"""Sectors: what a LucidNews installation watches (lot 47).

A sector is a whole pack: its categories (with labels and the one-line scope the AI reads),
and, as sectors are added, its editorial profile, its source catalog and its authorities. One
sector per installation, chosen by the administrator (``Config.sector``, Settings screen).

Category IDs are unique across all sectors. So an item keeps valid categories whatever the
current sector (the archive outlives a change of sector), while what is *shown* and *asked of
the AI* is the current sector's list only.

``tech`` is the original LucidNews taxonomy (``taxonomy.Category``) and stays the default.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .taxonomy import _ALIASES, CATEGORY_LABELS, CATEGORY_SCOPES, Category

DEFAULT_SECTOR = "tech"


@dataclass(frozen=True)
class SectorCategory:
    id: str
    labels: Dict[str, str]
    scope: str  # one line, in English: what the AI files under this category
    aliases: Tuple[str, ...] = ()

    def label(self, language: str) -> str:
        return self.labels.get(language, self.labels["en"])


@dataclass(frozen=True)
class Sector:
    id: str
    labels: Dict[str, str]
    descriptions: Dict[str, str]
    categories: Tuple[SectorCategory, ...]

    @property
    def category_ids(self) -> List[str]:
        return [category.id for category in self.categories]

    def label(self, language: str) -> str:
        return self.labels.get(language, self.labels["en"])

    def payload(self) -> Dict[str, object]:
        """What the web app needs: names and categories, never more."""
        return {
            "id": self.id,
            "labels": dict(self.labels),
            "descriptions": dict(self.descriptions),
            "categories": [{"id": category.id, "labels": dict(category.labels)} for category in self.categories],
        }


def _tech() -> Sector:
    aliases: Dict[Category, List[str]] = {}
    for alias, category in _ALIASES.items():
        aliases.setdefault(category, []).append(alias)
    return Sector(
        id="tech",
        labels={"en": "Technology & IT", "fr": "Tech et IT"},
        descriptions={
            "en": "AI, software, cloud, security, data and the rest of IT.",
            "fr": "IA, logiciel, cloud, sécurité, data et le reste de l'IT.",
        },
        categories=tuple(
            SectorCategory(category.value, dict(CATEGORY_LABELS[category]), CATEGORY_SCOPES[category], tuple(aliases.get(category, ())))
            for category in Category
        ),
    )


SECTORS: Dict[str, Sector] = {sector.id: sector for sector in (_tech(),)}


def get_sector(sector_id: str) -> Sector:
    """The sector, or the default one for an unknown ID (an old configuration stays readable)."""
    return SECTORS.get(sector_id, SECTORS[DEFAULT_SECTOR])


def all_categories() -> List[SectorCategory]:
    """Every category of every sector, sector by sector, in each sector's order."""
    return [category for sector in SECTORS.values() for category in sector.categories]


def _check_unique_ids() -> None:
    seen: Dict[str, str] = {}
    for sector in SECTORS.values():
        for category in sector.categories:
            if category.id in seen:
                raise ValueError(f"category {category.id} belongs to {seen[category.id]} and {sector.id}")
            seen[category.id] = sector.id


_check_unique_ids()
