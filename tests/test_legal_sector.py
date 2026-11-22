"""Phase 3 — the legal and regulatory sector: its domains (lot 3.1), its editorial profile
(lot 3.2) and its catalog of verified sources (lot 3.3)."""

import json

from lucidnews import sectors
from lucidnews.ai.prompting.analysis import analysis_system_prompt
from lucidnews.ai.prompting.enrichment import artifact_prompt, block_prompt
from lucidnews.models import Config
from lucidnews.reliability.assess import ReliabilityPolicy
from lucidnews.reliability.models import SourceTier
from lucidnews.sector_catalog import load_sector_catalog
from lucidnews.processing.profiles import ProfileRegistry
from lucidnews.sectors import NO_ADVICE_RULE
from lucidnews.taxonomy import category_label, normalize_categories
from tests.test_auth import ROOT

LEGAL_DOMAINS = [
    "legal-legislation",
    "legal-case-law",
    "legal-business",
    "legal-employment",
    "legal-data-protection",
    "legal-eu",
    "legal-compliance",
    "legal-public",
]


# Lot 3.1 — the domains --------------------------------------------------------------------------


def test_legal_has_its_eight_domains_in_order_with_both_languages() -> None:
    legal = sectors.get_sector("legal")
    assert legal.category_ids == LEGAL_DOMAINS
    assert legal.labels == {"en": "Legal & regulatory", "fr": "Juridique et réglementaire"}
    for category in legal.categories:
        assert category.labels["fr"] and category.labels["en"] and category.scope
    assert legal.nouns["fr"] == "juridique"
    assert legal.rules == (NO_ADVICE_RULE,)


def test_legal_words_land_on_legal_and_do_not_steal_other_sectors_words() -> None:
    sectors._check_unique_ids()
    assert normalize_categories(["Jurisprudence", "RGPD", "Droit européen"]) == ["legal-case-law", "legal-data-protection", "legal-eu"]
    assert normalize_categories(["conformité", "droit du travail", "droit public"]) == ["legal-compliance", "legal-employment", "legal-public"]
    # Words finance had first stay finance's, tech's stay tech's.
    assert normalize_categories(["compliance", "security"]) == ["finance-regulation", "cybersecurity"]
    assert category_label("legal-business", "fr") == "Droit des affaires"


def test_the_ai_reads_the_legal_scopes_and_only_them() -> None:
    profile = ProfileRegistry.load(ROOT / "profiles", "tech-news").get("tech-news")
    prompt = analysis_system_prompt(profile, sector="legal")
    for domain in LEGAL_DOMAINS:
        assert f"`{domain}`" in prompt
    assert "`finance-markets`" not in prompt and "`ai`" not in prompt


# Lot 3.2 — the legal profile --------------------------------------------------------------------

REGISTRY = ProfileRegistry.load(ROOT / "profiles", "tech-news")


def test_the_legal_profile_loads_next_to_the_others() -> None:
    legal = REGISTRY.get("legal-news")
    assert legal.definition.display_names["fr"] == "Actualités juridiques"
    assert [block.id for block in legal.definition.enrichment.blocks] == ["summary", "background", "impact"]


def test_the_legal_prompts_tell_a_bill_from_a_law_and_never_advise() -> None:
    legal = REGISTRY.get("legal-news")
    blocks = list(legal.definition.enrichment.blocks)
    analysis = analysis_system_prompt(legal, sector="legal")
    writing = [
        block_prompt(legal, "fr", blocks[0], include_header=True, sector="legal"),
        artifact_prompt(legal, "fr", blocks, sector="legal"),
    ]
    assert "a proposal or a bill is not a law" in analysis
    assert "entry-into-force date or a deadline only if the source gives it" in analysis
    for prompt in [analysis, *writing]:
        assert NO_ADVICE_RULE in prompt
    for prompt in writing:
        assert "never present a bill, a draft or an opinion as adopted law" in prompt


def test_the_legal_profile_turns_away_advice_and_marketing() -> None:
    match = REGISTRY.get("legal-news").match_prompt
    assert "legal advice" in match and "law firm marketing" in match


# Lot 3.3 — the sources --------------------------------------------------------------------------

REPORT = ROOT / "docs" / "sources" / "verification" / "legal-2026-11-22.md"


def test_the_legal_catalog_loads_and_every_domain_has_a_source() -> None:
    catalog = load_sector_catalog("legal")
    assert catalog.profile == "legal-news"
    sources = [*catalog.sources.rss, *catalog.sources.pages]
    assert 15 <= len(sources) <= 30  # 16 feeds and 4 official pages on 2026-11-22
    for source in sources:
        assert source.category in LEGAL_DOMAINS and source.profile == "legal-news", source.name
        assert str(source.url).startswith("https://"), source.name
    assert {source.category for source in sources} == set(LEGAL_DOMAINS)
    # Decision 12: the keyword searches are ready but off.
    assert not catalog.sources.gdelt.enabled and not catalog.sources.google_news.enabled


def test_the_texts_and_decisions_of_institutions_have_the_official_rank() -> None:
    raw = json.loads((ROOT / "data" / "config.example.json").read_text())
    raw["sector"] = "legal"
    policy = ReliabilityPolicy.for_config(Config.model_validate(raw))
    for host in ("www.conseil-etat.fr", "www.cnil.fr", "curia.europa.eu", "www.conseil-constitutionnel.fr", "www.edpb.europa.eu"):
        assert policy.tier_for_domain(host) == SourceTier.OFFICIAL, host
    assert policy.tier_for_domain("www.dalloz-actualite.fr") == SourceTier.REPUTABLE


def test_every_legal_source_was_kept_by_the_checker() -> None:
    report = REPORT.read_text(encoding="utf-8")
    catalog = load_sector_catalog("legal")
    for source in [*catalog.sources.rss, *catalog.sources.pages]:
        line = next(line for line in report.splitlines() if f"[{source.name}]" in line)
        assert "| gardée |" in line, line
    assert "écartée" not in report
