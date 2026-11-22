"""Changing the sector of an installation replaces its sources (chantier « Nouveaux secteurs »,
lot 1.4). Nothing is ever deleted:

- **listed sources** (RSS feeds, GitHub): each carries the sector it belongs to (``sector``; none
  means tech). On a switch, the enabled sources of other sectors are disabled and marked
  ``disabled_by_sector``; the new sector's ones are enabled again (only those the switch had
  disabled), and the catalog sources it does not have yet are added, tagged with the sector;
- **single sources** (Hacker News, Reddit, Telegram, X, OSS Insight, GDELT, Google News): the
  current settings are parked under ``sources.parked.<sector>``; the new sector gets back what it
  had parked, or its catalog's settings, or the same block switched off.

Switching to another sector and back gives the sources the installation had before.
"""

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .sector_catalog import SectorCatalog
from .sectors import DEFAULT_SECTOR

LISTED = ("rss", "pages", "github")
SINGLE = ("hackernews", "reddit", "telegram", "twitter", "ossinsight", "gdelt", "google_news")
DISABLED_BY_SECTOR = "disabled_by_sector"


@dataclass
class SwitchSummary:
    """What a switch does to the sources, said in numbers before it is confirmed."""

    added: List[str] = field(default_factory=list)
    enabled: List[str] = field(default_factory=list)
    disabled: List[str] = field(default_factory=list)

    def counts(self) -> Dict[str, int]:
        return {"added": len(self.added), "enabled": len(self.enabled), "disabled": len(self.disabled)}


def sector_of(entry: Dict[str, Any]) -> str:
    return entry.get("sector") or DEFAULT_SECTOR


def _label(kind: str, entry: Dict[str, Any]) -> str:
    if kind in ("rss", "pages"):
        return str(entry.get("name"))
    return "/".join(str(entry[key]) for key in ("owner", "repo", "username") if entry.get(key)) or str(entry.get("type"))


def _identity(kind: str, entry: Dict[str, Any]) -> tuple:
    if kind in ("rss", "pages"):
        return (str(entry.get("url", "")).rstrip("/").lower(),)
    return (entry.get("type"), str(entry.get("owner") or "").lower(), str(entry.get("repo") or "").lower(), str(entry.get("username") or "").lower())


def _catalog_lists(catalog: SectorCatalog) -> Dict[str, List[Dict[str, Any]]]:
    dumped = catalog.sources.model_dump(mode="json", exclude_none=True)
    return {kind: dumped.get(kind, []) for kind in LISTED}


def switch_sources(raw: Dict[str, Any], current: str, catalog: SectorCatalog) -> SwitchSummary:
    """Rewrite ``raw`` (the whole configuration file) for ``catalog.sector``, in place."""
    target = catalog.sector
    summary = SwitchSummary()
    sources = raw.setdefault("sources", {})

    for kind in LISTED:
        entries: List[Dict[str, Any]] = sources.setdefault(kind, [])
        for entry in entries:
            if sector_of(entry) != target and entry.get("enabled", True):
                entry["enabled"] = False
                entry[DISABLED_BY_SECTOR] = True
                summary.disabled.append(_label(kind, entry))
            elif sector_of(entry) == target and entry.pop(DISABLED_BY_SECTOR, False):
                entry["enabled"] = True
                summary.enabled.append(_label(kind, entry))
        present = {_identity(kind, entry) for entry in entries}
        for entry in _catalog_lists(catalog)[kind]:
            if _identity(kind, entry) in present:
                continue
            added = {**entry, "enabled": True}
            if target != DEFAULT_SECTOR:
                added["sector"] = target
            entries.append(added)
            summary.added.append(_label(kind, added))

    parked: Dict[str, Dict[str, Any]] = sources.setdefault("parked", {})
    outgoing = {key: copy.deepcopy(sources[key]) for key in SINGLE if key in sources}
    incoming = parked.pop(target, None)
    if incoming is None:
        from_catalog = catalog.sources.model_dump(mode="json", exclude_none=True, include=catalog.sources.model_fields_set)
        incoming = {key: from_catalog[key] for key in SINGLE if key in from_catalog}
    if outgoing:
        parked[current] = outgoing
    for key in SINGLE:
        if key in incoming:
            sources[key] = incoming[key]
        elif isinstance(sources.get(key), dict):
            sources[key] = {**sources[key], "enabled": False}
    if not parked:
        sources.pop("parked")
    return summary
