"""Phase 5 — the energy and climate sector: its domains (lot 5.1), its editorial profile
(lot 5.2), its catalog of verified sources (lot 5.3), and the official rank of published orders
and regulator deliberations (lot 5.4)."""

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

ENERGY_DOMAINS = [
    "energy-markets",
    "energy-renewables",
    "energy-efficiency",
    "energy-renovation",
    "energy-grids",
    "energy-regulation",
    "energy-climate",
    "energy-mobility",
]


# Lot 5.1 — the domains --------------------------------------------------------------------------


def test_energy_has_its_eight_domains_in_order_with_both_languages() -> None:
    energy = sectors.get_sector("energy")
    assert energy.category_ids == ENERGY_DOMAINS
    assert energy.labels == {"en": "Energy & climate", "fr": "Énergie et climat"}
    for category in energy.categories:
        assert category.labels["fr"] and category.labels["en"] and category.scope
    assert energy.nouns["fr"] == "énergie"
    assert energy.rules == (NO_ADVICE_RULE,)
    assert "white certificate" in energy.categories[2].scope  # the CEE, named for the AI


def test_energy_words_land_on_energy_and_do_not_steal_other_sectors_words() -> None:
    sectors._check_unique_ids()
    assert normalize_categories(["CEE", "MaPrimeRénov", "solaire"]) == ["energy-efficiency", "energy-renovation", "energy-renewables"]
    assert normalize_categories(["RSE", "batteries", "véhicules électriques"]) == ["energy-climate", "energy-grids", "energy-mobility"]
    assert normalize_categories(["Marchés de l'énergie", "nucléaire", "Réglementation énergie"]) == [
        "energy-markets",
        "energy-regulation",
    ]
    # The other sectors keep their words: "regulation" and "markets" stay finance, "RGPD" legal.
    assert normalize_categories(["regulation", "markets", "RGPD"]) == ["finance-regulation", "finance-markets", "legal-data-protection"]
    assert category_label("energy-efficiency", "fr") == "Efficacité énergétique et CEE"


def test_the_ai_reads_the_energy_scopes_and_only_them() -> None:
    profile = ProfileRegistry.load(ROOT / "profiles", "tech-news").get("tech-news")
    prompt = analysis_system_prompt(profile, sector="energy")
    for domain in ENERGY_DOMAINS:
        assert f"`{domain}`" in prompt
    assert "`health-drugs`" not in prompt and "`ai`" not in prompt


# Lot 5.2 — the energy profile -------------------------------------------------------------------

REGISTRY = ProfileRegistry.load(ROOT / "profiles", "tech-news")


def test_the_energy_profile_loads_next_to_the_others() -> None:
    energy = REGISTRY.get("energy-news")
    assert energy.definition.display_names["fr"] == "Actualités énergie"
    assert [block.id for block in energy.definition.enrichment.blocks] == ["summary", "background", "impact"]


def test_a_published_order_is_confirmed_and_a_deadline_is_never_invented() -> None:
    energy = REGISTRY.get("energy-news")
    blocks = list(energy.definition.enrichment.blocks)
    analysis = analysis_system_prompt(energy, sector="energy")
    writing = [
        block_prompt(energy, "fr", blocks[0], include_header=True, sector="energy"),
        artifact_prompt(energy, "fr", blocks, sector="energy"),
    ]
    assert "what changes for a professional: a new rule, an operation sheet, a price or a tariff, a deadline" in analysis
    assert "published in the official journal or by the authority that adopts it counts as confirmed" in analysis
    assert "Give a deadline, an entry-into-force date, a price or a volume only when the source gives it" in analysis
    for prompt in [analysis, *writing]:
        assert NO_ADVICE_RULE in prompt
    for prompt in writing:
        assert "Never cite a deadline or an entry-into-force date that the source does not give" in prompt
        assert "never present a draft as an adopted rule" in prompt


def test_the_energy_profile_turns_away_tips_and_price_predictions() -> None:
    match = REGISTRY.get("energy-news").match_prompt
    assert "investment tips" in match and "energy price predictions presented as facts" in match


# Lot 5.3 — the sources --------------------------------------------------------------------------

REPORT = ROOT / "docs" / "sources" / "verification" / "energy-2026-11-22.md"


def energy_policy() -> ReliabilityPolicy:
    raw = json.loads((ROOT / "data" / "config.example.json").read_text())
    raw["sector"] = "energy"
    return ReliabilityPolicy.for_config(Config.model_validate(raw))


def test_the_energy_catalog_loads_and_every_domain_has_a_source() -> None:
    catalog = load_sector_catalog("energy")
    assert catalog.profile == "energy-news"
    sources = [*catalog.sources.rss, *catalog.sources.pages]
    assert 15 <= len(sources) <= 30  # 21 feeds and 4 official pages on 2026-11-22
    for source in sources:
        assert source.category in ENERGY_DOMAINS and source.profile == "energy-news", source.name
        assert str(source.url).startswith("https://"), source.name
    assert {source.category for source in sources} == set(ENERGY_DOMAINS)
    assert not catalog.sources.gdelt.enabled and not catalog.sources.google_news.enabled  # decision 12


def test_every_energy_source_was_kept_by_the_checker() -> None:
    report = REPORT.read_text(encoding="utf-8")
    catalog = load_sector_catalog("energy")
    for source in [*catalog.sources.rss, *catalog.sources.pages]:
        line = next(line for line in report.splitlines() if f"[{source.name}]" in line)
        assert "| gardée |" in line, line
    assert "écartée" not in report


# Lot 5.4 — published orders and regulator deliberations have the official rank ----------------


def test_orders_and_deliberations_are_official_and_the_trade_press_is_not() -> None:
    policy = energy_policy()
    official = (
        "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000000000000",  # an order in the official journal
        "https://www.cre.fr/documents/deliberations/x.html",  # a deliberation of the regulator
        "https://www.ecologie.gouv.fr/politiques-publiques/dispositif-certificats-deconomies-denergie",
        "https://www.rte-france.com/actualites/x",
        "https://energy.ec.europa.eu/news/x_en",
    )
    for url in official:
        tier, _ = tier_for_url(url, policy)
        assert tier == SourceTier.OFFICIAL, url
        assert combine(tier, ClaimStatus.CONFIRMED) == ReliabilityLabel.CONFIRMED, url
    for press in ("https://www.revolution-energetique.com/x", "https://www.batiactu.com/x", "https://www.carbonbrief.org/x"):
        assert tier_for_url(press, policy)[0] == SourceTier.REPUTABLE, press
    # An energy company's own release stays below Confirmed.
    tier, _ = tier_for_url("https://www.totalenergies.com/fr/actualites/x", policy)
    assert combine(tier, ClaimStatus.CONFIRMED) != ReliabilityLabel.CONFIRMED
