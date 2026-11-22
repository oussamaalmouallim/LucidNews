"""Chantier « Nouveaux secteurs », lot 1.2 — what the AI is told depends on the sector: its
profile, and, outside tech, the rule that a news watch reports and never advises."""

import dataclasses

import pytest

from lucidnews import sectors
from lucidnews.ai.prompting.analysis import analysis_system_prompt
from lucidnews.ai.prompting.enrichment import artifact_prompt, block_prompt
from lucidnews.processing.profiles import ProfileRegistry
from lucidnews.sectors import NO_ADVICE_RULE
from tests.test_auth import ROOT
from tests.test_sectors import FAKE

PROFILE = ProfileRegistry.load(ROOT / "profiles", "tech-news").get("tech-news")
BLOCKS = PROFILE.definition.enrichment.blocks


def prompts(sector: str) -> list[str]:
    return [
        analysis_system_prompt(PROFILE, sector),
        block_prompt(PROFILE, "fr", BLOCKS[0], include_header=True, sector=sector),
        artifact_prompt(PROFILE, "fr", list(BLOCKS), sector=sector),
    ]


@pytest.fixture
def regulated(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setitem(sectors.SECTORS, "fake", dataclasses.replace(FAKE, rules=(NO_ADVICE_RULE,)))


def test_the_tech_prompts_are_exactly_what_they_were() -> None:
    for prompt in prompts("tech"):
        assert "# Sector rules" not in prompt and NO_ADVICE_RULE not in prompt
    # The defaults are the tech sector: callers that do not pass a sector are unchanged.
    assert analysis_system_prompt(PROFILE) == prompts("tech")[0]
    assert artifact_prompt(PROFILE, "fr", list(BLOCKS)) == prompts("tech")[2]


def test_a_regulated_sector_adds_the_no_advice_rule_to_every_prompt(regulated) -> None:
    for prompt in prompts("fake"):
        assert "# Sector rules" in prompt and NO_ADVICE_RULE in prompt
    assert "never give advice" in NO_ADVICE_RULE and "only if the source gives it" in NO_ADVICE_RULE


def test_the_sector_rules_come_before_the_output_contract(regulated) -> None:
    analysis = prompts("fake")[0]
    assert analysis.index("# Sector rules") < analysis.index("# Output contract")
