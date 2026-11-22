"""The catalog of a sector (chantier « Nouveaux secteurs », lot 1.1): what an installation that
switches to this sector is given.

One file per sector, ``data/sectors/<sector>.json``:

- ``profile``: the editorial profile (``profiles/<id>/``) the AI uses for this sector;
- ``authorities``: publisher domains of the sector's authorities and their tier
  (``official``, ``reputable``…), added to the trust registry while the sector is active;
- ``sources``: the sector's sources, in the same shape as ``sources`` in ``config.json``
  (RSS feeds, GitHub, GDELT and Google News queries…). Every feed carries a ``category`` of the
  sector. Only sources checked by the source checker belong here;
- or ``sources_from``: a file of ``data/`` whose ``sources`` block is the catalog. The tech sector
  uses it to keep ``config.example.json`` as its one list of sources.

A catalog that names an unknown profile, a category of another sector or a malformed address is
refused when it is loaded: a sector never ships half valid.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import SourcesConfig
from .reliability.models import SourceTier
from .sectors import get_sector

PROJECT_DATA = Path(__file__).resolve().parents[1] / "data"
PROJECT_PROFILES = Path(__file__).resolve().parents[1] / "profiles"
DOMAIN = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


class CatalogError(ValueError):
    """A sector catalog that cannot be used, with the reason."""


@dataclass(frozen=True)
class SectorCatalog:
    sector: str
    profile: str
    sources: SourcesConfig
    authorities: Dict[str, SourceTier] = field(default_factory=dict)

    def categories_used(self) -> List[str]:
        used = [feed.category for feed in self.sources.rss if feed.category]
        used += [page.category for page in self.sources.pages if page.category]
        used += [repo.category for repo in self.sources.github if repo.category]
        return used


def _read(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogError(f"no catalog file: {path.name}") from exc
    except ValueError as exc:
        raise CatalogError(f"{path.name}: not valid JSON ({exc})") from exc
    if not isinstance(value, dict):
        raise CatalogError(f"{path.name}: expected a JSON object")
    return value


def load_sector_catalog(
    sector_id: str, data_dir: Optional[Path] = None, profiles_dir: Optional[Path] = None
) -> SectorCatalog:
    data_dir = data_dir or PROJECT_DATA
    profiles_dir = profiles_dir or PROJECT_PROFILES
    sector = get_sector(sector_id)
    if sector.id != sector_id:
        raise CatalogError(f"unknown sector: {sector_id}")
    path = data_dir / "sectors" / f"{sector_id}.json"
    raw = _read(path)

    profile = raw.get("profile")
    if not isinstance(profile, str) or not (profiles_dir / profile / "profile.json").is_file():
        raise CatalogError(f"{path.name}: unknown profile {profile!r}")

    if "sources_from" in raw:
        reference = raw["sources_from"]
        if not isinstance(reference, str) or "/" in reference or "\\" in reference:
            raise CatalogError(f"{path.name}: sources_from must be a file name of data/")
        sources_raw = _read(data_dir / reference).get("sources", {})
    else:
        sources_raw = raw.get("sources", {})
    try:
        sources = SourcesConfig.model_validate(sources_raw)
    except ValueError as exc:
        raise CatalogError(f"{path.name}: invalid sources ({exc})") from exc

    authorities: Dict[str, SourceTier] = {}
    for domain, tier in (raw.get("authorities") or {}).items():
        if not isinstance(domain, str) or not DOMAIN.match(domain):
            raise CatalogError(f"{path.name}: not a domain name: {domain!r}")
        try:
            authorities[domain] = SourceTier(tier)
        except ValueError as exc:
            raise CatalogError(f"{path.name}: unknown tier {tier!r} for {domain}") from exc

    catalog = SectorCatalog(sector_id, profile, sources, authorities)
    foreign = sorted({category for category in catalog.categories_used() if category not in sector.category_ids})
    if foreign:
        raise CatalogError(f"{path.name}: categories outside the {sector_id} sector: {', '.join(foreign)}")
    return catalog
