"""Chantier « Nouveaux secteurs », lot 1.3 — the authorities of the installation's sector are
official sources; outside that sector they are not, and the configuration has the last word."""

import json
import shutil

import pytest

from lucidnews import sector_catalog, sectors
from lucidnews.models import Config
from lucidnews.reliability.assess import ReliabilityPolicy
from lucidnews.reliability.models import SourceTier
from tests.test_auth import ROOT
from tests.test_sectors import FAKE


@pytest.fixture
def project(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setitem(sectors.SECTORS, "fake", FAKE)
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "sectors", data / "sectors")
    shutil.copy(ROOT / "data" / "config.example.json", data / "config.example.json")
    catalog = {"profile": "tech-news", "authorities": {"amf-france.org": "official", "agefi.fr": "reputable"}, "sources": {}}
    (data / "sectors" / "fake.json").write_text(json.dumps(catalog))
    monkeypatch.setattr(sector_catalog, "PROJECT_DATA", data)
    return data


def config(sector: str = "tech", domains: dict | None = None) -> Config:
    raw = json.loads((ROOT / "data" / "config.example.json").read_text())
    raw["sector"] = sector
    raw.setdefault("reliability", {})["domains"] = domains or {}
    return Config.model_validate(raw)


def test_an_authority_of_the_sector_is_an_official_source(project) -> None:
    policy = ReliabilityPolicy.for_config(config("fake"))
    assert policy.tier_for_domain("www.amf-france.org") == SourceTier.OFFICIAL
    assert policy.tier_for_domain("agefi.fr") == SourceTier.REPUTABLE
    assert policy.tier_for_domain("openai.com") == SourceTier.OFFICIAL  # the built-in list stays


def test_outside_its_sector_an_authority_is_unknown(project) -> None:
    assert ReliabilityPolicy.for_config(config("tech")).tier_for_domain("amf-france.org") == SourceTier.UNKNOWN


def test_the_configuration_has_the_last_word(project) -> None:
    policy = ReliabilityPolicy.for_config(config("fake", {"amf-france.org": "community"}))
    assert policy.tier_for_domain("amf-france.org") == SourceTier.COMMUNITY


def test_a_sector_without_catalog_keeps_the_built_in_list(project) -> None:
    (project / "sectors" / "fake.json").unlink()
    policy = ReliabilityPolicy.for_config(config("fake"))
    assert policy.tier_for_domain("amf-france.org") == SourceTier.UNKNOWN
    assert policy.tier_for_domain("openai.com") == SourceTier.OFFICIAL


def test_tech_is_exactly_the_former_registry() -> None:
    tech = config("tech")
    assert ReliabilityPolicy.for_config(tech) == ReliabilityPolicy.with_overrides(tech.reliability.domains, tech.reliability.accounts)


def test_an_announcement_by_an_authority_can_be_confirmed(project) -> None:
    from lucidnews.models import ClaimAssessment
    from lucidnews.reliability.assess import assess_item
    from lucidnews.reliability.models import ReliabilityLabel
    from tests.test_web_api import make_item

    item = make_item("amf", "tech-news", 9.0)
    item.url = "https://www.amf-france.org/fr/actualites/communique"
    item.processing.analysis.claim = ClaimAssessment(status="confirmed", evidence="published by the AMF")
    assert assess_item(item, ReliabilityPolicy.for_config(config("fake"))).label == ReliabilityLabel.CONFIRMED
    assert assess_item(item, ReliabilityPolicy.for_config(config("tech"))).label != ReliabilityLabel.CONFIRMED
