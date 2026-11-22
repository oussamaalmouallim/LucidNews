"""Chantier « Nouveaux secteurs », lot 1.1 — the catalog of a sector: its profile, its sources
and its authorities, refused as a whole when any part of it is wrong."""

import json
import shutil

import pytest

from lucidnews import sectors
from lucidnews.reliability.models import SourceTier
from lucidnews.sector_catalog import CatalogError, load_sector_catalog
from lucidnews.source_catalog import load_catalog
from tests.test_auth import ROOT
from tests.test_sectors import FAKE

FEED = {"name": "Marchés Hebdo", "url": "https://example.org/marches.xml", "category": "fake-markets"}


@pytest.fixture
def data_dir(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """A data directory with the fake sector registered and a valid catalog for it."""
    monkeypatch.setitem(sectors.SECTORS, "fake", FAKE)
    (tmp_path / "sectors").mkdir()
    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.example.json")
    write(tmp_path, {"profile": "tech-news", "authorities": {"amf-france.org": "official"}, "sources": {"rss": [FEED]}})
    return tmp_path


def write(data_dir, catalog) -> None:  # type: ignore[no-untyped-def]
    (data_dir / "sectors" / "fake.json").write_text(json.dumps(catalog))


def test_the_tech_catalog_is_the_example_configuration_unchanged() -> None:
    catalog = load_sector_catalog("tech")
    example = json.loads((ROOT / "data" / "config.example.json").read_text())["sources"]
    assert catalog.profile == "tech-news" and catalog.authorities == {}
    assert [feed.name for feed in catalog.sources.rss] == [feed["name"] for feed in example["rss"]]
    assert len(catalog.sources.rss) == 31 and len(catalog.sources.github) == 4


def test_every_registered_sector_ships_a_valid_catalog() -> None:
    for sector_id in sectors.SECTORS:
        assert load_sector_catalog(sector_id).sector == sector_id


def test_the_tech_recommendations_are_unchanged() -> None:
    entries = load_catalog()
    assert entries == load_catalog(sector="tech")
    assert {entry.origin for entry in entries} == {"example", "presets"}
    assert len(entries) > 31


def test_a_sector_catalog_gives_its_profile_sources_and_authorities(data_dir) -> None:
    catalog = load_sector_catalog("fake", data_dir)
    assert catalog.profile == "tech-news"
    assert [feed.name for feed in catalog.sources.rss] == ["Marchés Hebdo"]
    assert catalog.authorities == {"amf-france.org": SourceTier.OFFICIAL}
    entries = load_catalog(data_dir, sector="fake")
    assert [(entry.label, entry.category, entry.origin) for entry in entries] == [("Marchés Hebdo", "fake-markets", "sector")]


@pytest.mark.parametrize(
    "change, reason",
    [
        ({"profile": "no-such-profile"}, "unknown profile"),
        ({"sources": {"rss": [{**FEED, "category": "ai"}]}}, "categories outside the fake sector: ai"),
        ({"sources": {"rss": [{**FEED, "url": "not an address"}]}}, "invalid sources"),
        ({"authorities": {"https://amf-france.org/": "official"}}, "not a domain name"),
        ({"authorities": {"amf-france.org": "very-trusted"}}, "unknown tier"),
        ({"sources_from": "../secrets.json"}, "sources_from must be a file name"),
    ],
)
def test_a_wrong_catalog_is_refused_with_its_reason(data_dir, change, reason) -> None:
    write(data_dir, {"profile": "tech-news", "authorities": {}, "sources": {"rss": [FEED]}, **change})
    with pytest.raises(CatalogError, match=reason):
        load_sector_catalog("fake", data_dir)


def test_a_missing_or_broken_file_is_refused(data_dir) -> None:
    (data_dir / "sectors" / "fake.json").write_text("{not json")
    with pytest.raises(CatalogError, match="not valid JSON"):
        load_sector_catalog("fake", data_dir)
    (data_dir / "sectors" / "fake.json").unlink()
    with pytest.raises(CatalogError, match="no catalog file"):
        load_sector_catalog("fake", data_dir)
    with pytest.raises(CatalogError, match="unknown sector"):
        load_sector_catalog("astrology", data_dir)
