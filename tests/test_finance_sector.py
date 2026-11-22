"""Phase 2 — the finance sector: its domains (lot 2.1), its editorial profile (lot 2.2) and its
catalog of verified sources (lot 2.3)."""

from lucidnews import sectors
from lucidnews.ai.prompting.analysis import analysis_system_prompt
from lucidnews.ai.prompting.enrichment import artifact_prompt, block_prompt
from lucidnews.processing.profiles import ProfileRegistry
from lucidnews.reliability.models import SourceTier
from lucidnews.sector_catalog import load_sector_catalog
from lucidnews.sectors import NO_ADVICE_RULE
from lucidnews.taxonomy import category_label, normalize_categories
from tests.test_auth import ROOT

FINANCE_DOMAINS = [
    "finance-markets",
    "finance-banking",
    "finance-insurance",
    "finance-crypto",
    "finance-deals",
    "finance-macro",
    "finance-regulation",
    "finance-fintech",
]


# Lot 2.1 — the domains --------------------------------------------------------------------------


def test_finance_has_its_eight_domains_in_order_with_both_languages() -> None:
    finance = sectors.get_sector("finance")
    assert finance.id == "finance"
    assert finance.category_ids == FINANCE_DOMAINS
    for category in finance.categories:
        assert category.labels["fr"] and category.labels["en"]
        assert category.scope  # what the AI reads
    assert finance.nouns == {"en": "finance", "fr": "finance"}
    assert finance.rules == (NO_ADVICE_RULE,)


def test_finance_ids_are_unique_and_do_not_steal_tech_words() -> None:
    sectors._check_unique_ids()
    # Tech words still land on tech, finance words on finance.
    assert normalize_categories(["LLM", "security", "web"]) == ["ai", "cybersecurity", "web"]
    assert normalize_categories(["bourse", "Banques", "bitcoin", "M&A", "inflation"]) == [
        "finance-markets",
        "finance-banking",
        "finance-crypto",
    ]
    assert normalize_categories(["macro", "Régulation financière", "fintech"]) == [
        "finance-macro",
        "finance-regulation",
        "finance-fintech",
    ]
    assert category_label("finance-deals", "fr") == "Fusions et acquisitions"


def test_the_ai_reads_the_finance_scopes_and_only_them() -> None:
    profile = ProfileRegistry.load(ROOT / "profiles", "tech-news").get("tech-news")
    prompt = analysis_system_prompt(profile, sector="finance")
    for domain in FINANCE_DOMAINS:
        assert f"`{domain}`" in prompt
    assert "`ai`" not in prompt
    assert "never give advice" in prompt


def test_the_web_app_gets_the_finance_names() -> None:
    payload = sectors.get_sector("finance").payload()
    assert [category["id"] for category in payload["categories"]] == FINANCE_DOMAINS
    assert payload["labels"]["fr"] == "Finance"
    assert "scope" not in payload["categories"][0]


# Lot 2.2 — the finance profile ------------------------------------------------------------------

REGISTRY = ProfileRegistry.load(ROOT / "profiles", "tech-news")


def test_the_finance_profile_loads_next_to_the_tech_ones() -> None:
    finance = REGISTRY.get("finance-news")
    assert finance.definition.display_names["fr"] == "Actualités finance"
    assert [block.id for block in finance.definition.enrichment.blocks] == ["summary", "background", "impact"]
    assert {"tech-news", "tech-blog", "ai-creator", "finance-news"} <= REGISTRY.ids


def test_the_finance_prompts_score_like_a_careful_analyst_and_never_advise() -> None:
    finance = REGISTRY.get("finance-news")
    blocks = list(finance.definition.enrichment.blocks)
    analysis = analysis_system_prompt(finance, sector="finance")
    writing = [
        block_prompt(finance, "fr", blocks[0], include_header=True, sector="finance"),
        artifact_prompt(finance, "fr", blocks, sector="finance"),
    ]
    assert "careful analyst" in analysis and "central bank" in analysis
    assert "A forecast, an analyst's target or an opinion is never a fact" in analysis
    for prompt in [analysis, *writing]:
        assert NO_ADVICE_RULE in prompt  # the sector rule, in every prompt
    for prompt in writing:
        assert "Never write a recommendation to buy, sell or hold" in prompt
    # The finance profile does not leak into tech.
    tech = REGISTRY.get("tech-news")
    assert "careful analyst" not in analysis_system_prompt(tech, sector="tech")


def test_the_finance_profile_turns_away_tips_and_predictions() -> None:
    match = REGISTRY.get("finance-news").match_prompt
    assert "investment tips" in match and "price predictions" in match


# Lot 2.3 — the sources --------------------------------------------------------------------------

REPORT = ROOT / "docs" / "sources" / "verification" / "finance-2026-11-22.md"


def test_the_finance_catalog_loads_with_its_profile_and_only_finance_domains() -> None:
    catalog = load_sector_catalog("finance")
    assert catalog.profile == "finance-news"
    sources = [*catalog.sources.rss, *catalog.sources.pages]
    assert 15 <= len(sources) <= 30  # 26 feeds and 1 official page on 2026-11-22
    for source in sources:
        assert source.category in FINANCE_DOMAINS, source.name
        assert source.profile == "finance-news", source.name
        assert str(source.url).startswith("https://"), source.name
    # Every domain has at least one source.
    assert {source.category for source in sources} == set(FINANCE_DOMAINS)
    # The keyword searches are ready but off: in a real collection (lot 2.4) GDELT brought 75 news
    # of unknown sites in every language and Google News investment tips, then refused (429).
    for search in (catalog.sources.gdelt, catalog.sources.google_news):
        assert search is not None and not search.enabled
    assert "banque centrale" in catalog.sources.gdelt.query and "central bank" in catalog.sources.gdelt.query


def test_the_finance_authorities_count_as_official_and_the_press_as_reputable() -> None:
    authorities = load_sector_catalog("finance").authorities
    for regulator in ("ecb.europa.eu", "amf-france.org", "sec.gov", "esma.europa.eu", "federalreserve.gov"):
        assert authorities[regulator] == SourceTier.OFFICIAL
    for press in ("lemonde.fr", "coindesk.com", "insurancejournal.com"):
        assert authorities[press] == SourceTier.REPUTABLE


def test_every_finance_source_was_kept_by_the_checker() -> None:
    report = REPORT.read_text(encoding="utf-8")
    catalog = load_sector_catalog("finance")
    for source in [*catalog.sources.rss, *catalog.sources.pages]:
        line = next(line for line in report.splitlines() if f"[{source.name}]" in line)
        assert "| gardée |" in line, line
    assert "écartée" not in report
