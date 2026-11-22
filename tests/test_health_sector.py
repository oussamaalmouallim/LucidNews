"""Phase 4 — the health and pharma sector: its domains (lot 4.1), its editorial profile
(lot 4.2) and its catalog of verified sources (lot 4.3)."""

import json

from lucidnews import sectors
from lucidnews.ai.prompting.analysis import analysis_system_prompt
from lucidnews.ai.prompting.enrichment import artifact_prompt, block_prompt
from lucidnews.models import Config
from lucidnews.processing.profiles import ProfileRegistry
from lucidnews.reliability.assess import ReliabilityPolicy, combine, tier_for_url
from lucidnews.reliability.models import ClaimStatus, ReliabilityLabel, SourceTier
from lucidnews.sector_catalog import load_sector_catalog
from lucidnews.sectors import NO_ADVICE_RULE
from lucidnews.taxonomy import category_label, normalize_categories
from tests.test_auth import ROOT

HEALTH_DOMAINS = [
    "health-regulation",
    "health-drugs",
    "health-trials",
    "health-devices",
    "health-public",
    "health-digital",
    "health-biotech",
    "health-care",
]


# Lot 4.1 — the domains --------------------------------------------------------------------------


def test_health_has_its_eight_domains_in_order_with_both_languages() -> None:
    health = sectors.get_sector("health")
    assert health.category_ids == HEALTH_DOMAINS
    assert health.labels == {"en": "Health & pharma", "fr": "Santé et pharma"}
    for category in health.categories:
        assert category.labels["fr"] and category.labels["en"] and category.scope
    assert health.nouns["fr"] == "santé"
    assert health.rules == (NO_ADVICE_RULE,)


def test_health_words_land_on_health_and_do_not_steal_other_sectors_words() -> None:
    sectors._check_unique_ids()
    assert normalize_categories(["vaccins", "essais cliniques", "medtech"]) == ["health-drugs", "health-trials", "health-devices"]
    assert normalize_categories(["santé publique", "E-santé", "biotech"]) == ["health-public", "health-digital", "health-biotech"]
    assert normalize_categories(["RGPD", "fintech", "LLM"]) == ["legal-data-protection", "finance-fintech", "ai"]
    assert category_label("health-care", "fr") == "Établissements de santé"


def test_the_ai_reads_the_health_scopes_and_only_them() -> None:
    profile = ProfileRegistry.load(ROOT / "profiles", "tech-news").get("tech-news")
    prompt = analysis_system_prompt(profile, sector="health")
    for domain in HEALTH_DOMAINS:
        assert f"`{domain}`" in prompt
    assert "`legal-eu`" not in prompt and "`ai`" not in prompt


# Lot 4.2 — the health profile -------------------------------------------------------------------

REGISTRY = ProfileRegistry.load(ROOT / "profiles", "tech-news")


def test_the_health_profile_loads_next_to_the_others() -> None:
    health = REGISTRY.get("health-news")
    assert health.definition.display_names["fr"] == "Actualités santé"
    assert [block.id for block in health.definition.enrichment.blocks] == ["summary", "background", "impact"]


def test_a_lab_announcement_stays_unverified_and_the_ai_never_advises() -> None:
    health = REGISTRY.get("health-news")
    blocks = list(health.definition.enrichment.blocks)
    analysis = analysis_system_prompt(health, sector="health")
    writing = [
        block_prompt(health, "fr", blocks[0], include_header=True, sector="health"),
        artifact_prompt(health, "fr", blocks, sector="health"),
    ]
    assert "A company's own announcement of its trial results, a press release or a preprint is not proof" in analysis
    assert "treat the claim as unverified" in analysis
    assert "An approval counts as confirmed only when the authority that grants it" in analysis
    for prompt in [analysis, *writing]:
        assert NO_ADVICE_RULE in prompt
    for prompt in writing:
        assert "never present a company's claim as an established result" in prompt


def test_the_health_profile_turns_away_tips_and_miracle_claims() -> None:
    match = REGISTRY.get("health-news").match_prompt
    assert "medical advice" in match and "miracle-cure claims" in match


# Lot 4.3 — the sources --------------------------------------------------------------------------

REPORT = ROOT / "docs" / "sources" / "verification" / "health-2026-11-22.md"


def health_policy() -> ReliabilityPolicy:
    raw = json.loads((ROOT / "data" / "config.example.json").read_text())
    raw["sector"] = "health"
    return ReliabilityPolicy.for_config(Config.model_validate(raw))


def test_the_health_catalog_loads_and_every_domain_has_a_source() -> None:
    catalog = load_sector_catalog("health")
    assert catalog.profile == "health-news"
    sources = [*catalog.sources.rss, *catalog.sources.pages]
    assert 15 <= len(sources) <= 30  # 20 feeds and 2 official pages on 2026-11-22
    for source in sources:
        assert source.category in HEALTH_DOMAINS and source.profile == "health-news", source.name
        assert str(source.url).startswith("https://"), source.name
    assert {source.category for source in sources} == set(HEALTH_DOMAINS)
    assert not catalog.sources.gdelt.enabled and not catalog.sources.google_news.enabled  # decision 12


def test_every_health_source_was_kept_by_the_checker() -> None:
    report = REPORT.read_text(encoding="utf-8")
    catalog = load_sector_catalog("health")
    for source in [*catalog.sources.rss, *catalog.sources.pages]:
        line = next(line for line in report.splitlines() if f"[{source.name}]" in line)
        assert "| gardée |" in line, line
    assert "écartée" not in report


# Lot 4.4 — a laboratory's announcement alone is never "Confirmed" -------------------------------


def test_an_authority_confirms_a_lab_announcement_alone_never_does() -> None:
    policy = health_policy()
    for authority in ("https://www.ema.europa.eu/en/news/x", "https://ansm.sante.fr/actualites/x", "https://www.has-sante.fr/jcms/x"):
        tier, _ = tier_for_url(authority, policy)
        assert combine(tier, ClaimStatus.CONFIRMED) == ReliabilityLabel.CONFIRMED, authority
    # The company's own press release, even if the AI read it as "confirmed", stays below Confirmed.
    for lab in ("https://www.pfizer.com/news/press-release/x", "https://www.sanofi.com/fr/medias/x", "https://www.modernatx.com/x"):
        tier, _ = tier_for_url(lab, policy)
        assert tier == SourceTier.UNKNOWN, lab
        assert combine(tier, ClaimStatus.CONFIRMED) != ReliabilityLabel.CONFIRMED, lab
    # A journal or the trade press is reliable, not official.
    assert tier_for_url("https://www.nejm.org/doi/x", policy)[0] == SourceTier.REPUTABLE
    assert tier_for_url("https://www.statnews.com/x", policy)[0] == SourceTier.REPUTABLE
