"""AI quota and token budget: the run never blocks, and only an exhausted quota
publishes items without analysis."""

import asyncio
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console

import lucidnews.orchestrator as orchestrator_module
from lucidnews.ai import budget
from lucidnews.ai.analyzer import ContentAnalyzer
from lucidnews.ai.budget import AILimit, QuotaExhausted, is_quota_exhausted_error
from lucidnews.ai.client import QuotaGuardClient
from lucidnews.ai.summarizer import DailySummarizer
from lucidnews.ai.tokens import record_usage
from lucidnews.archive import ItemArchive
from lucidnews.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentArtifact,
    ContentBlock,
    ContentItem,
    ProcessingResult,
    SourceType,
)
from lucidnews.newsletter import plan_deliveries
from lucidnews.newsletter.models import DigestPreferences, Subscriber
from lucidnews.newsletter.selection import matches_unanalyzed
from lucidnews.orchestrator import PipelineOrchestrator
from lucidnews.processing import ProfileRegistry
from lucidnews.reliability import ReliabilityLabel, SourceTier
from lucidnews.reliability.assess import ReliabilityPolicy, assess_item
from lucidnews.web_api import ApiContext, edition_payload, resolve

PROFILES = ProfileRegistry.load(Path(__file__).resolve().parents[1] / "profiles", "tech-news")
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)

GEMINI_DAILY = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota', "
    "'details': [{'violations': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}]}}"
)
GEMINI_MINUTE = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota', "
    "'details': [{'violations': [{'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier'}]}]}}"
)


def make_item(item_id: str, url: str = "https://example.com/a", *, hours_ago: int = 1) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=f"Headline {item_id}",
        url=url,
        published_at=NOW - timedelta(hours=hours_ago),
        profile="tech-news",
    )


def skipped(item: ContentItem) -> ContentItem:
    item.processing = ProcessingResult(
        classification=ClassificationResult(profile="tech-news", method="source_override"),
        ai_skipped=AILimit.PROVIDER_QUOTA,
    )
    item.processing.reliability = assess_item(item)
    return item


class FakeInner:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls = 0

    async def complete(self, system, user, temperature=None, max_tokens=None):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.error:
            raise self.error
        return '{"score": 8, "reason": "r", "summary": "s"}'


# Detection ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        GEMINI_DAILY,
        "Error code: 429 - {'error': {'code': 'insufficient_quota'}}",
        "Error code: 402 - {'error': {'message': 'Insufficient Balance'}}",
        "Your credit balance is too low to access the Anthropic API.",
        "All providers failed. Last error: " + GEMINI_DAILY,
    ],
)
def test_exhausted_quota_errors_are_recognized(message: str) -> None:
    assert is_quota_exhausted_error(RuntimeError(message))


@pytest.mark.parametrize(
    "message",
    [GEMINI_MINUTE, "Error code: 429 - rate_limit_exceeded", "503 Service Unavailable", "bad JSON"],
)
def test_transient_errors_are_not_an_exhausted_quota(message: str) -> None:
    assert not is_quota_exhausted_error(RuntimeError(message))


# Guard -------------------------------------------------------------------------


def test_guard_stops_calling_the_provider_once_the_quota_is_gone() -> None:
    inner = FakeInner(RuntimeError(GEMINI_DAILY))
    client = QuotaGuardClient(inner)

    for _ in range(3):
        with pytest.raises(QuotaExhausted):
            asyncio.run(client.complete("s", "u"))

    assert inner.calls == 1  # later calls fail immediately, nothing waits
    assert budget.exhausted() is AILimit.PROVIDER_QUOTA


def test_guard_lets_transient_errors_through() -> None:
    client = QuotaGuardClient(FakeInner(RuntimeError(GEMINI_MINUTE)))

    with pytest.raises(RuntimeError, match="PerMinute"):
        asyncio.run(client.complete("s", "u"))
    assert budget.exhausted() is None


def test_token_budget_stops_the_ai_for_the_rest_of_the_run() -> None:
    budget.start_run(1000)
    inner = FakeInner()
    client = QuotaGuardClient(inner)

    asyncio.run(client.complete("s", "u"))
    record_usage("gemini", input_tokens=900, output_tokens=200)

    with pytest.raises(QuotaExhausted):
        asyncio.run(client.complete("s", "u"))
    assert inner.calls == 1
    assert budget.exhausted() is AILimit.TOKEN_BUDGET
    assert budget.tokens_used() == 1100


def test_budget_counts_only_the_current_run() -> None:
    record_usage("gemini", input_tokens=5000)
    budget.start_run(1000)

    assert budget.tokens_used() == 0
    budget.ensure_available()


# Analysis ----------------------------------------------------------------------


def test_analysis_skips_items_without_retrying_once_the_quota_is_gone() -> None:
    inner = FakeInner(RuntimeError(GEMINI_DAILY))
    analyzer = ContentAnalyzer(QuotaGuardClient(inner), PROFILES, console=Console(file=StringIO()))
    items = [make_item("a", "https://openai.com/index/a"), make_item("b"), make_item("c")]
    items[2].profile = "auto"

    asyncio.run(analyzer.analyze_batch(items))

    assert inner.calls == 1  # no tenacity retry, no call after the first quota error
    for item in items:
        assert item.processing.analysis is None
        assert item.processing.ai_skipped is AILimit.PROVIDER_QUOTA
        # Never presented as a fact, even from an official publisher.
        assert item.processing.reliability.label is ReliabilityLabel.UNVERIFIED
    assert items[0].processing.reliability.source_tier is SourceTier.OFFICIAL
    # An "auto" item gets a placeholder profile that the classifier redoes later.
    assert items[2].processing.classification.method == "unclassified"


def test_quota_during_reanalysis_keeps_the_existing_analysis() -> None:
    budget.mark_exhausted(AILimit.PROVIDER_QUOTA)
    analyzer = ContentAnalyzer(QuotaGuardClient(FakeInner()), PROFILES, console=Console(file=StringIO()))
    item = make_item("a")
    item.processing = ProcessingResult(
        classification=ClassificationResult(profile="tech-news", method="source_override"),
        analysis=ContentAnalysis(score=8.0, reason="r", summary="s"),
    )

    asyncio.run(analyzer.analyze_batch([item]))

    assert item.processing.analysis.score == 8.0
    assert item.processing.ai_skipped is None


def test_successful_analysis_clears_a_previous_skip() -> None:
    analyzer = ContentAnalyzer(QuotaGuardClient(FakeInner()), PROFILES, console=Console(file=StringIO()))
    item = skipped(make_item("a"))

    asyncio.run(analyzer.analyze_batch([item]))

    assert item.processing.analysis.score == 8.0
    assert item.processing.ai_skipped is None


# Orchestrator ------------------------------------------------------------------


def make_orchestrator(**digest) -> PipelineOrchestrator:  # type: ignore[no-untyped-def]
    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.console = Console(file=StringIO())
    orchestrator.icons = PipelineOrchestrator.icons
    orchestrator.archive = None
    orchestrator.reliability_policy = ReliabilityPolicy()
    orchestrator.config = SimpleNamespace(
        ai=SimpleNamespace(failed_retry_delay_sec=30, languages=["en", "fr"]),
        digest=SimpleNamespace(unanalyzed_max_items=digest.get("limit", 15)),
        reliability=SimpleNamespace(exclude_labels=digest.get("exclude", [])),
        archive=SimpleNamespace(reuse_enrichment=True),
    )
    return orchestrator


def test_unanalyzed_items_are_published_only_when_the_quota_ran_out() -> None:
    items = [skipped(make_item("a"))]

    assert make_orchestrator().select_unanalyzed_items(items) == []

    budget.mark_exhausted(AILimit.TOKEN_BUDGET)
    assert make_orchestrator().select_unanalyzed_items(items) == items


def test_unanalyzed_items_favor_known_publishers_then_recent_ones() -> None:
    budget.mark_exhausted(AILimit.PROVIDER_QUOTA)
    old_official = skipped(make_item("old-official", "https://openai.com/x", hours_ago=10))
    new_unknown = skipped(make_item("new-unknown", "https://example.com/y", hours_ago=1))
    reputable = skipped(make_item("reputable", "https://lwn.net/z", hours_ago=5))
    analyzed = make_item("analyzed")
    analyzed.processing = ProcessingResult(
        classification=ClassificationResult(profile="tech-news", method="source_override"),
        analysis=ContentAnalysis(score=None, reason="Analysis failed", summary="x"),
    )
    items = [new_unknown, analyzed, reputable, old_official]

    selected = make_orchestrator(limit=2).select_unanalyzed_items(items)

    assert [item.id for item in selected] == ["old-official", "reputable"]
    assert make_orchestrator(limit=0).select_unanalyzed_items(items) == []
    assert make_orchestrator(exclude=[ReliabilityLabel.UNVERIFIED]).select_unanalyzed_items(items) == []


def test_no_deferred_retry_once_the_quota_is_gone(monkeypatch) -> None:
    sleeps = []

    async def fake_sleep(seconds):  # type: ignore[no-untyped-def]
        sleeps.append(seconds)

    monkeypatch.setattr(orchestrator_module.asyncio, "sleep", fake_sleep)
    budget.mark_exhausted(AILimit.PROVIDER_QUOTA)

    assert asyncio.run(make_orchestrator()._pause_before_retry(5, "analysis")) is False
    assert sleeps == []


def enriched(item: ContentItem, languages: list[str]) -> ContentItem:
    item.processing = ProcessingResult(
        classification=ClassificationResult(profile="tech-news", method="source_override"),
        analysis=ContentAnalysis(score=8.0, reason="r", summary="s"),
        artifacts={
            lang: ContentArtifact(
                language=lang,
                title="t",
                blocks=[ContentBlock(id="summary", title="S", content="c", primary=True)],
            )
            for lang in languages
        },
    )
    return item


def test_enrichment_is_reused_when_every_language_is_there(monkeypatch) -> None:
    batches = []

    class FakeEnricher:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            pass

        async def enrich_batch(self, items):  # type: ignore[no-untyped-def]
            from lucidnews.ai.enricher import EnrichmentBatchResult

            batches.append([item.id for item in items])
            return EnrichmentBatchResult(succeeded_ids=[item.id for item in items])

    monkeypatch.setattr(orchestrator_module, "ContentEnricher", FakeEnricher)
    monkeypatch.setattr(orchestrator_module, "create_ai_client", lambda config: None)
    orchestrator = make_orchestrator()
    orchestrator.profiles = SimpleNamespace()
    orchestrator.storage = SimpleNamespace(summaries_dir=None)
    complete = enriched(make_item("complete"), ["en", "fr"])
    partial = enriched(make_item("partial"), ["en"])

    result = asyncio.run(orchestrator.enrich_items([complete, partial]))

    assert batches == [["partial"]]
    assert result.succeeded_ids == ["complete", "partial"]


def test_enrichment_reuse_can_be_disabled(monkeypatch) -> None:
    orchestrator = make_orchestrator()
    orchestrator.config.archive.reuse_enrichment = False

    assert orchestrator._reusable_enrichments([enriched(make_item("a"), ["en", "fr"])]) == []


# Archive -----------------------------------------------------------------------


def test_skipped_items_use_no_attempt_and_come_back_next_run(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(hours=24))
    item = skipped(make_item("a"))
    archive.record_items(run_id, [item], selected=True)
    archive.finish_run(run_id, "success", ai_limit="provider_quota", tokens_used=1234)

    attempts, error = archive.item_attempts("a")
    assert attempts == 0 and error == "ai_skipped:provider_quota"
    pending = archive.pending_items(
        first_seen_after=datetime.now(timezone.utc) - timedelta(hours=1), max_attempts=3
    )
    assert [entry.id for entry in pending] == ["a"]
    assert pending[0].processing.ai_skipped is AILimit.PROVIDER_QUOTA

    run = archive.get_run(run_id)
    assert (run.ai_limit, run.tokens_used, run.ai_skipped_count) == ("provider_quota", 1234, 1)


# Rendering ---------------------------------------------------------------------


def test_digest_lists_unanalyzed_items_apart_with_a_warning() -> None:
    item = skipped(make_item("a"))
    item.title = "Leak: *new* model [soon]"

    summary = asyncio.run(
        DailySummarizer().generate_summary([], "2026-10-09", 40, language="fr", unanalyzed=[item])
    )

    assert "analyse IA désactivée, ou quota épuisé" in summary
    assert "## ⚠️ Sans analyse IA" in summary
    assert "ni résumé, ni score, ni vérification" in summary
    assert r"Leak: \*new\* model \[soon\]" in summary  # original headline, escaped
    assert "/10" not in summary  # no score


def test_digest_without_quota_issue_is_unchanged() -> None:
    summary = asyncio.run(DailySummarizer().generate_summary([], "2026-10-09", 40))

    assert "Not analyzed" not in summary
    assert "none met the importance threshold" in summary


def test_newsletter_sends_unanalyzed_items_only_to_unfiltered_subscribers() -> None:
    item = skipped(make_item("a"))
    item.metadata["feed_name"] = "LWN"

    assert matches_unanalyzed(item, DigestPreferences())
    assert matches_unanalyzed(item, DigestPreferences(sources=["lwn"]))
    assert not matches_unanalyzed(item, DigestPreferences(sources=["github"]))
    assert not matches_unanalyzed(item, DigestPreferences(categories=["security"]))
    assert not matches_unanalyzed(item, DigestPreferences(min_importance="high"))
    assert not matches_unanalyzed(item, DigestPreferences(include_unconfirmed=False))

    analyzed = enriched(make_item("b"), ["en"])
    analyzed.processing.reliability = assess_item(analyzed)
    subscriber = Subscriber(email="a@example.com", preferences=DigestPreferences(max_items=1))
    plan = plan_deliveries([subscriber], [], ["en"], unanalyzed=[item])
    assert plan.deliveries[0].unanalyzed == [item]
    plan = plan_deliveries([subscriber], [analyzed], ["en"], unanalyzed=[item])
    assert plan.deliveries[0].unanalyzed == []  # max_items counts the analyzed items first


def test_edition_keeps_unanalyzed_items_out_of_the_sections(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(hours=24))
    analyzed = enriched(make_item("analyzed"), ["en"])
    analyzed.processing.reliability = assess_item(analyzed)
    unknown = skipped(make_item("raw", hours_ago=1))
    official = skipped(make_item("raw-official", "https://openai.com/x", hours_ago=9))
    archive.record_items(run_id, [analyzed, unknown, official], selected=True)
    archive.finish_run(run_id, "success", ai_limit="token_budget", tokens_used=50)
    ctx = ApiContext(archive=archive)

    payload = edition_payload(ctx, archive.get_run(run_id), "en")

    assert [item["id"] for section in payload["sections"] for item in section["items"]] == ["analyzed"]
    assert [item["id"] for item in payload["unanalyzed"]] == ["raw-official", "raw"]
    raw = payload["unanalyzed"][1]
    assert raw["ai_skipped"] is True and raw["score"] is None and raw["summary"] == ""
    assert raw["reliability"]["label"] == "unverified"
    assert (payload["ai_limit"], payload["tokens_used"], payload["ai_skipped_count"]) == ("token_budget", 50, 2)


def test_unanalyzed_items_carry_the_usual_domain_of_their_source(tmp_path) -> None:
    """The edition groups news by domain: an unanalyzed one goes under its source's domain, if known."""
    from lucidnews.source_catalog import CatalogEntry

    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(hours=24))
    known, unknown = skipped(make_item("known")), skipped(make_item("unknown", hours_ago=2))
    known.metadata["source_key"], unknown.metadata["source_key"] = "rss:ai-blog", "rss:elsewhere"
    archive.record_items(run_id, [known, unknown], selected=True)
    archive.finish_run(run_id, "success", ai_limit="disabled")
    catalog = [CatalogEntry("rss:ai-blog", "rss", "AI blog", "ai", {}, None, "example")]
    ctx = ApiContext(archive=archive, catalog=catalog)

    payload = edition_payload(ctx, archive.get_run(run_id), "en")

    assert {item["id"]: item["source_domain"] for item in payload["unanalyzed"]} == {"known": "ai", "unknown": None}
    assert edition_payload(ctx, archive.get_run(run_id), "en")["unanalyzed"] == payload["unanalyzed"]  # cached


def test_an_unanalyzed_item_has_its_own_page(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(hours=24))
    archive.record_items(run_id, [skipped(make_item("raw"))], selected=True)
    archive.finish_run(run_id, "success", ai_limit="provider_quota")

    status, payload = resolve(ApiContext(archive=archive), "/api/items/raw", {"lang": ["fr"]})

    assert status == 200
    assert payload["ai_skipped"] is True and payload["claim"] is None
    assert [edition["id"] for edition in payload["editions"]] == [run_id]


# AI turned off (ai.enabled) ----------------------------------------------------


def test_with_the_ai_turned_off_no_client_is_created_and_items_are_listed_unanalyzed(monkeypatch) -> None:
    def forbidden(config):  # type: ignore[no-untyped-def]
        raise AssertionError("no AI client may be created while the AI is off")

    monkeypatch.setattr(orchestrator_module, "create_ai_client", forbidden)
    orchestrator = make_orchestrator()
    orchestrator.profiles = PROFILES
    orchestrator.config.ai.enabled = False
    assert orchestrator._ai_enabled() is False
    budget.start_run(None)
    budget.mark_exhausted(AILimit.DISABLED)
    items = [make_item("a", "https://lwn.net/a"), make_item("b", "https://example.com/b")]

    analyzed = asyncio.run(orchestrator.analyze_items(items))

    assert all(item.processing.ai_skipped is AILimit.DISABLED for item in analyzed)
    assert all(item.processing.analysis is None and item.processing.reliability is not None for item in analyzed)
    assert [item.id for item in orchestrator.select_unanalyzed_items(analyzed)] == ["a", "b"]
    # Nothing was enriched either: only analyzed items reach that stage.
    assert asyncio.run(orchestrator.enrich_items([])).succeeded_count == 0


def test_the_ai_is_off_by_default_in_a_fresh_configuration() -> None:
    from lucidnews.models import AIConfig

    config = AIConfig(provider="gemini", model="m", api_key_env="K")
    assert config.enabled is False


def test_with_the_ai_off_nothing_else_calls_the_ai_either(monkeypatch) -> None:
    def forbidden(config):  # type: ignore[no-untyped-def]
        raise AssertionError("no AI client may be created while the AI is off")

    monkeypatch.setattr(orchestrator_module, "create_ai_client", forbidden)
    orchestrator = make_orchestrator()
    orchestrator.config.sources = SimpleNamespace(twitter=None)
    budget.start_run(None)
    budget.mark_exhausted(AILimit.DISABLED)
    # Items analyzed in an earlier run (reused from the archive) still reach these stages.
    analyzed = [enriched(make_item("a"), ["en"]), enriched(make_item("b", "https://example.com/b"), ["en"])]

    assert asyncio.run(orchestrator.merge_topic_duplicates(analyzed)) == analyzed
    assert asyncio.run(orchestrator.enrich_items(analyzed)).succeeded_count == 0


def test_an_enabled_ai_without_a_key_does_not_stop_the_run(monkeypatch) -> None:
    def no_key(config):  # type: ignore[no-untyped-def]
        raise ValueError("Missing API key environment variable configured by ai.api_key_env.")

    monkeypatch.setattr(orchestrator_module, "create_ai_client", no_key)
    orchestrator = make_orchestrator()
    orchestrator.profiles = PROFILES
    budget.start_run(None)
    items = [make_item("a")]

    analyzed = asyncio.run(orchestrator.analyze_items(items))

    assert analyzed[0].processing.ai_skipped is AILimit.DISABLED
    assert budget.exhausted() is AILimit.DISABLED
