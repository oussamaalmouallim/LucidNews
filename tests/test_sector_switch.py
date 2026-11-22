"""Chantier « Nouveaux secteurs », lot 1.4 — changing the sector replaces the sources: the new
sector's are enabled or added, the others switched off, nothing deleted, and a round trip gives
back the sources the installation had."""

import copy
import json

import pytest

from lucidnews import sectors
from lucidnews.models import Config, SourcesConfig
from lucidnews.sector_catalog import SectorCatalog, load_sector_catalog
from lucidnews.sector_switch import switch_sources
from tests.test_auth import ROOT
from tests.test_sectors import FAKE

FAKE_FEEDS = [
    {"name": "Marchés", "url": "https://example.org/marches.xml", "category": "fake-markets"},
    {"name": "Banque", "url": "https://example.org/banque.xml", "category": "fake-banking"},
]
FAKE_CATALOG = SectorCatalog(
    "fake",
    "tech-news",
    SourcesConfig.model_validate({"rss": FAKE_FEEDS, "gdelt": {"enabled": True, "query": "banque OR bourse"}}),
)


@pytest.fixture(autouse=True)
def fake_sector(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setitem(sectors.SECTORS, "fake", FAKE)


def example() -> dict:
    return json.loads((ROOT / "data" / "config.example.json").read_text())


def enabled(raw: dict) -> dict:
    """What would run: enabled listed sources, and the enabled single sources."""
    sources = raw["sources"]
    listed = {kind: sorted(entry.get("name") or entry.get("repo") or "" for entry in sources.get(kind, []) if entry.get("enabled", True)) for kind in ("rss", "github")}
    single = sorted(key for key, block in sources.items() if isinstance(block, dict) and key != "parked" and block.get("enabled", True))
    return {**listed, "single": single}


def test_switching_enables_the_sector_sources_and_switches_the_others_off() -> None:
    raw = example()
    on_before = sum(1 for kind in ("rss", "github") for entry in raw["sources"][kind] if entry.get("enabled", True))
    summary = switch_sources(raw, "tech", FAKE_CATALOG)
    assert enabled(raw) == {"rss": ["Banque", "Marchés"], "github": [], "single": ["gdelt"]}
    assert summary.counts() == {"added": 2, "enabled": 0, "disabled": on_before}
    assert all(feed["sector"] == "fake" for feed in raw["sources"]["rss"] if feed["name"] in ("Marchés", "Banque"))
    assert raw["sources"]["gdelt"]["query"] == "banque OR bourse"
    Config.model_validate({**raw, "sector": "fake"})  # the file stays a valid configuration


def test_nothing_is_deleted_and_a_round_trip_gives_the_sources_back() -> None:
    raw = example()
    before = enabled(raw)
    names_before = [feed["name"] for feed in raw["sources"]["rss"]]
    switch_sources(raw, "tech", FAKE_CATALOG)
    back = switch_sources(raw, "fake", load_sector_catalog("tech"))
    assert enabled(raw) == before
    assert back.counts()["added"] == 0 and back.counts()["disabled"] == 2
    assert [feed["name"] for feed in raw["sources"]["rss"]][: len(names_before)] == names_before
    assert raw["sources"]["hackernews"] == example()["sources"]["hackernews"]  # parked and given back
    assert not any(feed.get("disabled_by_sector") for feed in raw["sources"]["rss"] if not feed.get("sector"))


def test_a_source_switched_off_by_hand_stays_off_on_return() -> None:
    raw = example()
    raw["sources"]["rss"][0]["enabled"] = False
    switch_sources(raw, "tech", FAKE_CATALOG)
    switch_sources(raw, "fake", load_sector_catalog("tech"))
    assert raw["sources"]["rss"][0]["enabled"] is False


def test_a_second_visit_reuses_the_sector_sources_instead_of_adding_them_again() -> None:
    raw = example()
    switch_sources(raw, "tech", FAKE_CATALOG)
    switch_sources(raw, "fake", load_sector_catalog("tech"))
    again = switch_sources(raw, "tech", FAKE_CATALOG)
    assert again.counts()["added"] == 0 and again.counts()["enabled"] == 2
    assert [feed["name"] for feed in raw["sources"]["rss"]].count("Marchés") == 1


def test_a_preview_changes_nothing() -> None:
    raw = example()
    snapshot = copy.deepcopy(raw)
    switch_sources(copy.deepcopy(raw), "tech", FAKE_CATALOG)
    assert raw == snapshot


def test_official_pages_switch_with_their_sector() -> None:
    page = {"name": "Autorité", "url": "https://autorite.example/communiques", "item_selector": "li", "category": "fake-markets"}
    catalog = SectorCatalog("fake", "tech-news", SourcesConfig.model_validate({"rss": FAKE_FEEDS, "pages": [page]}))
    raw = example()
    assert "Autorité" in switch_sources(raw, "tech", catalog).added
    assert raw["sources"]["pages"][0]["sector"] == "fake" and raw["sources"]["pages"][0]["enabled"] is True
    switch_sources(raw, "fake", load_sector_catalog("tech"))
    assert raw["sources"]["pages"][0]["enabled"] is False and raw["sources"]["pages"][0]["disabled_by_sector"] is True
