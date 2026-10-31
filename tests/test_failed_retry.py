import asyncio
from datetime import datetime, timezone
from io import StringIO
from types import SimpleNamespace

from rich.console import Console

import lucidnews.orchestrator as orchestrator_module
from lucidnews.ai.enricher import EnrichmentBatchResult
from lucidnews.models import ClassificationResult, ContentAnalysis, ContentItem, ProcessingResult, SourceType
from lucidnews.orchestrator import PipelineOrchestrator
from lucidnews.reliability.assess import ReliabilityPolicy


def make_item(item_id: str) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=item_id,
        url=f"https://example.com/{item_id}",
        published_at=datetime(2026, 10, 6, tzinfo=timezone.utc),
        processing=ProcessingResult(
            classification=ClassificationResult(profile="tech-news", method="source_override")
        ),
    )


def make_orchestrator(delay):  # type: ignore[no-untyped-def]
    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.console = Console(file=StringIO())
    orchestrator.icons = PipelineOrchestrator.icons
    orchestrator.archive = None
    orchestrator.profiles = SimpleNamespace()
    orchestrator.storage = SimpleNamespace(summaries_dir=None)
    orchestrator.reliability_policy = ReliabilityPolicy()
    orchestrator.config = SimpleNamespace(
        ai=SimpleNamespace(failed_retry_delay_sec=delay, languages=["en"]),
        archive=None,
        sector="tech",
    )
    return orchestrator


def test_failed_analyses_get_one_deferred_retry(monkeypatch) -> None:
    attempts: dict[str, int] = {}

    class FakeAnalyzer:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            pass

        async def analyze_batch(self, items):  # type: ignore[no-untyped-def]
            for item in items:
                attempts[item.id] = attempts.get(item.id, 0) + 1
                ok = item.id == "good" or (item.id == "flaky" and attempts[item.id] == 2)
                item.processing.analysis = ContentAnalysis(
                    score=8.0 if ok else None, reason="r", summary="s"
                )
            return items

    monkeypatch.setattr(orchestrator_module, "ContentAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(orchestrator_module, "create_ai_client", lambda config: None)
    items = [make_item("good"), make_item("flaky"), make_item("broken")]

    asyncio.run(make_orchestrator(0).analyze_items(items))

    assert attempts == {"good": 1, "flaky": 2, "broken": 2}
    assert [item.processing.analysis.score for item in items] == [8.0, 8.0, None]


def test_retry_can_be_disabled(monkeypatch) -> None:
    calls = []

    class FakeAnalyzer:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            pass

        async def analyze_batch(self, items):  # type: ignore[no-untyped-def]
            calls.append([item.id for item in items])
            for item in items:
                item.processing.analysis = ContentAnalysis(score=None, reason="r", summary="s")
            return items

    monkeypatch.setattr(orchestrator_module, "ContentAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(orchestrator_module, "create_ai_client", lambda config: None)

    asyncio.run(make_orchestrator(None).analyze_items([make_item("a")]))

    assert calls == [["a"]]


def test_failed_enrichments_get_one_deferred_retry(monkeypatch) -> None:
    batches = []

    class FakeEnricher:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            pass

        async def enrich_batch(self, items):  # type: ignore[no-untyped-def]
            batches.append([item.id for item in items])
            if len(batches) == 1:
                return EnrichmentBatchResult(succeeded_ids=["a"], failures={"b": "429", "c": "429"})
            return EnrichmentBatchResult(succeeded_ids=["b"], failures={"c": "bad JSON"})

    monkeypatch.setattr(orchestrator_module, "ContentEnricher", FakeEnricher)
    monkeypatch.setattr(orchestrator_module, "create_ai_client", lambda config: None)

    result = asyncio.run(
        make_orchestrator(0).enrich_items([make_item("a"), make_item("b"), make_item("c")])
    )

    assert batches == [["a", "b", "c"], ["b", "c"]]
    assert result.succeeded_ids == ["a", "b"]
    assert result.failures == {"c": "bad JSON"}
