"""Lot 47 — sectors: one installation watches one sector, chosen in Settings. Tech is the
original taxonomy and the default; a change of sector keeps the archive readable."""

import json

import pytest

from lucidnews import sectors
from lucidnews.ai.prompting.analysis import analysis_system_prompt
from lucidnews.auth.passwords import hash_password
from lucidnews.coverage import CoverageThresholds, compute_coverage
from lucidnews.models import Config
from lucidnews.processing.profiles import ProfileRegistry
from lucidnews.sectors import Sector, SectorCategory
from lucidnews.taxonomy import Category, category_label, normalize_categories
from tests.test_auth import PASSWORD, ROOT, Client, start_api

FAKE = Sector(
    id="fake",
    labels={"en": "Fake sector", "fr": "Secteur factice"},
    descriptions={"en": "For tests.", "fr": "Pour les tests."},
    categories=(
        SectorCategory("fake-markets", {"en": "Markets", "fr": "Marchés"}, "stock and bond markets", ("bourse",)),
        SectorCategory("fake-banking", {"en": "Banking", "fr": "Banque"}, "banks and lending"),
    ),
)


@pytest.fixture
def two_sectors(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setitem(sectors.SECTORS, "fake", FAKE)
    yield


def example_config(**changes) -> dict:  # type: ignore[no-untyped-def]
    raw = json.loads((ROOT / "data" / "config.example.json").read_text())
    raw.update(changes)
    return raw


# The tech sector is the original taxonomy, unchanged ------------------------------------------


def test_tech_is_the_default_and_keeps_the_original_categories_in_order() -> None:
    tech = sectors.get_sector("tech")
    assert sectors.DEFAULT_SECTOR == "tech"
    assert tech.category_ids == [category.value for category in Category]
    assert Config.model_validate(example_config()).sector == "tech"
    assert normalize_categories(["LLM", "Cybersécurité", "unknown", "web"]) == ["ai", "cybersecurity", "web"]


def test_category_ids_are_unique_across_sectors(two_sectors, monkeypatch) -> None:
    sectors._check_unique_ids()
    clash = Sector("clash", {"en": "C"}, {"en": "C"}, (SectorCategory("ai", {"en": "AI"}, "x"),))
    monkeypatch.setitem(sectors.SECTORS, "clash", clash)
    with pytest.raises(ValueError):
        sectors._check_unique_ids()


# Configuration --------------------------------------------------------------------------------


def test_an_unknown_sector_is_refused() -> None:
    with pytest.raises(ValueError):
        Config.model_validate(example_config(sector="astrology"))


def test_watched_domains_follow_the_sector(two_sectors) -> None:
    config = Config.model_validate(example_config(sector="fake"))
    assert config.digest.watched_categories == ["fake-markets", "fake-banking"]
    raw = example_config(sector="fake")
    raw.setdefault("digest", {})["watched_categories"] = ["ai"]
    with pytest.raises(ValueError, match="not categories of the fake sector"):
        Config.model_validate(raw)


# What the AI is asked, and what the archive keeps --------------------------------------------


def test_the_ai_is_offered_the_categories_of_the_sector_only(two_sectors) -> None:
    profile = ProfileRegistry.load(ROOT / "profiles", "tech-news").profiles[0]
    tech, fake = analysis_system_prompt(profile, "tech"), analysis_system_prompt(profile, "fake")
    assert "`cybersecurity`" in tech and "`fake-markets`" not in tech
    assert "`fake-markets`: stock and bond markets" in fake and "`cybersecurity`" not in fake
    assert analysis_system_prompt(profile) == tech  # the default is unchanged


def test_news_of_a_former_sector_keep_their_categories_and_labels(two_sectors) -> None:
    assert normalize_categories(["ai", "fake-markets", "Banque"]) == ["ai", "fake-markets", "fake-banking"]
    assert normalize_categories(["bourse"]) == ["fake-markets"]
    assert category_label("fake-banking", "fr") == "Banque" and category_label("ai", "en") == "AI / LLM / Agents"


def test_coverage_lists_the_categories_it_is_given() -> None:
    result = compute_coverage([], set(), {}, [], CoverageThresholds(), categories=["web", "ai"])
    assert [row["category"] for row in result["categories"]] == ["web", "ai"]
    assert len(compute_coverage([], set(), {}, [], CoverageThresholds())["categories"]) == len(Category)


# The web app: reading the sector, changing it ---------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch, two_sectors):  # type: ignore[no-untyped-def]
    ctx, server = start_api(tmp_path, monkeypatch)
    ctx.auth.db.create_user("admin@example.com", "Admin", password_hash=hash_password(PASSWORD), role="admin")
    admin, reader = Client(server), Client(server)
    assert admin.sign_in("admin@example.com")[0] == 200
    assert reader.sign_up()[0] == 201
    yield ctx, tmp_path, admin, reader
    server.shutdown()
    server.server_close()


def test_a_reader_reads_the_sector_and_its_categories(api) -> None:
    _, _, _, reader = api
    status, body, _ = reader.request("GET", "/api/sector")
    assert status == 200 and body["sector"]["id"] == "tech"
    assert body["sector"]["categories"][0] == {"id": "ai", "labels": {"en": "AI / LLM / Agents", "fr": "IA / LLM / Agents"}}
    assert {sector["id"] for sector in body["sectors"]} == {"tech", "fake"}


def test_only_an_administrator_changes_the_sector(api) -> None:
    _, _, _, reader = api
    status, body, _ = reader.request("PUT", "/api/settings/sector", {"sector": "fake"})
    assert (status, body["code"]) == (403, "admin_only")


def test_changing_the_sector_rewrites_the_configuration_and_is_served_at_once(api) -> None:
    ctx, tmp_path, admin, reader = api
    raw = json.loads((tmp_path / "config.json").read_text())
    raw.setdefault("digest", {})["watched_categories"] = ["ai", "web"]
    (tmp_path / "config.json").write_text(json.dumps(raw))

    status, body, _ = admin.request("PUT", "/api/settings/sector", {"sector": "fake"})
    assert status == 200 and body["sector"]["id"] == "fake"
    written = json.loads((tmp_path / "config.json").read_text())
    assert written["sector"] == "fake" and written["digest"]["watched_categories"] == ["fake-markets", "fake-banking"]
    assert reader.request("GET", "/api/sector")[1]["sector"]["categories"][0]["id"] == "fake-markets"
    assert list((tmp_path / "backups").glob("config-*.json"))  # the previous file is kept

    assert admin.request("PUT", "/api/settings/sector", {"sector": "tech"})[1]["sector"]["id"] == "tech"


def test_an_unknown_sector_is_refused_by_the_api(api) -> None:
    _, tmp_path, admin, _ = api
    before = (tmp_path / "config.json").read_text()
    status, body, _ = admin.request("PUT", "/api/settings/sector", {"sector": "astrology"})
    assert (status, body["error"]) == (422, "unknown sector")
    assert (tmp_path / "config.json").read_text() == before
