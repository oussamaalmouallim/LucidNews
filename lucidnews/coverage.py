"""Coverage of the taxonomy categories by the sources, from the archive (lot 18).

Every number comes from archived items: the categories the AI gave them, the
source that collected them, whether a run published them and their reliability
label. A category is a *gap* when the reader watches it and, over the period,
fewer configured sources fed it than ``min_sources`` or it got fewer analyzed
items than ``min_items``.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set

from .models import ContentItem
from .reliability import ReliabilityLabel
from .source_quality import item_source_key
from .sectors import DEFAULT_SECTOR, get_sector

TRUSTED_LABELS = {ReliabilityLabel.CONFIRMED, ReliabilityLabel.RELIABLE}
TOP_SOURCES = 6


@dataclass(frozen=True)
class CoverageThresholds:
    min_sources: int = 2
    min_items: int = 3


def compute_coverage(
    items: Iterable[ContentItem],
    published_ids: Set[str],
    configured_sources: Mapping[str, str],
    watched: Sequence[str],
    thresholds: CoverageThresholds,
    policy: Optional[object] = None,
    categories: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """Per-category coverage, in taxonomy order, plus totals for the period.

    ``configured_sources``: enabled source keys (``configured_source_keys``).
    ``policy``: a ReliabilityPolicy to label items with the current registry.
    """
    from .reliability.assess import assess_item

    analyzed: List[ContentItem] = []
    unanalyzed = 0
    for item in items:
        analysis = item.processing.analysis if item.processing else None
        if analysis is None or analysis.score is None:
            unanalyzed += 1
            continue
        analyzed.append(item)

    def trusted(item: ContentItem) -> bool:
        reliability = assess_item(item, policy) if policy is not None else item.processing.reliability  # type: ignore[union-attr]
        return reliability is not None and reliability.label in TRUSTED_LABELS

    rows = []
    for category in categories if categories is not None else get_sector(DEFAULT_SECTOR).category_ids:
        members = [item for item in analyzed if category in item.processing.analysis.categories]  # type: ignore[union-attr]
        by_source = Counter(item_source_key(item) for item in members)
        active = sorted(key for key in by_source if key in configured_sources)
        is_watched = category in watched
        reasons = []
        if is_watched and len(active) < thresholds.min_sources:
            reasons.append("sources")
        if is_watched and len(members) < thresholds.min_items:
            reasons.append("items")
        rows.append(
            {
                "category": category,
                "watched": is_watched,
                "gap": bool(reasons),
                "gap_reasons": reasons,
                "items": len(members),
                "published": sum(1 for item in members if item.id in published_ids),
                "active_sources": len(active),
                "sources": [
                    {"source": key, "items": count, "configured": key in configured_sources}
                    for key, count in by_source.most_common(TOP_SOURCES)
                ],
                "latest_at": max((item.published_at for item in members), default=None),
                "trusted_share": (
                    round(sum(1 for item in members if trusted(item)) / len(members), 4) if members else None
                ),
            }
        )
    for entry in rows:
        if entry["latest_at"] is not None:
            entry["latest_at"] = entry["latest_at"].isoformat()  # type: ignore[union-attr]
    return {
        "analyzed": len(analyzed),
        "unanalyzed": unanalyzed,
        "uncategorized": sum(1 for item in analyzed if not item.processing.analysis.categories),  # type: ignore[union-attr]
        "categories": rows,
    }
