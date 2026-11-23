"""Lot 6.2 — the documentation's links lead to files that exist. Only links inside the project are
checked (no web address, no anchor-only link); an anchor after a file name is ignored."""

import re
from pathlib import Path

import pytest

from tests.test_auth import ROOT

DOCS = [
    ROOT / "README.md",
    ROOT / "docs" / "secteurs.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "lots.md",
    ROOT / "docs" / "plans" / "2026-11-21-nouveaux-secteurs.md",
]
LINK = re.compile(r"\]\(([^)\s]+)\)")


def local_links(doc: Path) -> list[str]:
    text = re.sub(r"```.*?```", "", doc.read_text(encoding="utf-8"), flags=re.S)  # code blocks are not links
    return [
        target.split("#", 1)[0]
        for target in LINK.findall(text)
        if not target.startswith(("http://", "https://", "mailto:", "#"))
    ]


@pytest.mark.parametrize("doc", DOCS, ids=lambda doc: doc.name)
def test_every_local_link_of_the_documentation_leads_to_a_file(doc: Path) -> None:
    missing = [target for target in local_links(doc) if not (doc.parent / target).exists()]
    assert missing == [], f"{doc.relative_to(ROOT)}: {missing}"


def test_the_sectors_guide_names_every_installed_sector_and_its_report() -> None:
    from lucidnews.sectors import SECTORS

    guide = (ROOT / "docs" / "secteurs.md").read_text(encoding="utf-8")
    for sector in SECTORS.values():
        assert f"`{sector.id}`" in guide and sector.labels["fr"] in guide, sector.id
        assert (ROOT / "docs" / "sources" / "verification" / f"{sector.id}-2026-11-22.md").exists(), sector.id
