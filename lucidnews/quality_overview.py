"""Quality of the watch on one page (lot 19): indicators computed from the archive.

Every number comes from archived runs, items and per-source outcomes of the
period. Where the archive has no data (runs recorded before a counter existed,
no published item, no annotation), the indicator says so with ``None`` and a
count of what is missing, never with an estimate.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .archive import ItemArchive
from .coverage import CoverageThresholds, compute_coverage
from .evaluation.metrics import MIN_RELIABLE_SAMPLE
from .models import ContentItem, DigestConfig
from .reliability import ReliabilityLabel
from .source_health import HealthStatus, assess_health
from .source_quality import item_source_key

RECENT_ERRORS = 5
FRESH_HOURS = 24


def _hours(later: str, earlier: datetime) -> float:
    start = datetime.fromisoformat(later)
    if earlier.tzinfo is None:
        earlier = earlier.replace(tzinfo=timezone.utc)
    return max((start - earlier).total_seconds() / 3600, 0.0)


def _percentile(values: List[float], share: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(share * (len(ordered) - 1))))
    return ordered[index]


def _label(item: ContentItem, policy: Optional[object]) -> Optional[ReliabilityLabel]:
    from .reliability.assess import assess_item

    processing = item.processing
    if processing is None or processing.ai_skipped is not None or processing.analysis is None:
        return None
    reliability = assess_item(item, policy) if policy is not None else processing.reliability  # type: ignore[arg-type]
    return reliability.label if reliability is not None else None


def quality_overview(
    archive: ItemArchive,
    *,
    days: int,
    configured_sources: Mapping[str, str],
    digest: DigestConfig,
    policy: Optional[object] = None,
    evaluation: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
    categories: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    runs = archive.runs_since(since)
    published = archive.published_since(since)
    source_rows = archive.source_run_rows(since)

    # Coverage (lot 18) ---------------------------------------------------------------
    coverage = compute_coverage(
        archive.items_between(since),
        {item.id for _, item in published},
        configured_sources,
        digest.watched_categories,
        CoverageThresholds(digest.coverage_min_sources, digest.coverage_min_items),
        policy,
        categories,
    )
    watched = [entry for entry in coverage["categories"] if entry["watched"]]

    # Diversity ------------------------------------------------------------------------
    collected = Counter()
    for row in source_rows:
        if configured_sources and row["source_key"] not in configured_sources:
            continue
        collected[row["source_key"]] += int(row["fetched_count"] or 0)
    unique_published: Dict[str, ContentItem] = {}
    for _, item in published:
        unique_published[item.id] = item
    published_by_source = Counter(item_source_key(item) for item in unique_published.values())

    def top(counter: Counter) -> Optional[Dict[str, Any]]:
        total = sum(counter.values())
        if not total:
            return None
        key, count = counter.most_common(1)[0]
        return {"source": key, "count": count, "share": round(count / total, 4)}

    # Source health ----------------------------------------------------------------------
    health = assess_health(source_rows)
    if configured_sources:
        health = [entry for entry in health if entry.source_key in configured_sources]
    seen = {entry.source_key for entry in health}
    errors = [
        {"source": row["source_key"], "error": row["error"], "at": row["started_at"]}
        for row in source_rows
        if row["status"] == "failure" and (not configured_sources or row["source_key"] in configured_sources)
    ][:RECENT_ERRORS]

    # Freshness: age of each published item when its run started ------------------------
    ages = [_hours(started_at, item.published_at) for started_at, item in published]

    # Selection counters (recorded from lot 19 on) -------------------------------------
    with_stats = [run for run in runs if run.above_threshold_count is not None]

    # Reliability of what was published ------------------------------------------------
    labels = Counter()
    unanalyzed = 0
    for item in unique_published.values():
        if item.processing is not None and item.processing.ai_skipped is not None:
            unanalyzed += 1
            continue
        label = _label(item, policy)
        labels[label.value if label else "none"] += 1

    return {
        "days": days,
        "since": since.isoformat(),
        "runs": len(runs),
        "published": len(unique_published),
        "coverage": {
            "watched": len(watched),
            "gaps": [entry["category"] for entry in watched if entry["gap"]],
            "analyzed": coverage["analyzed"],
        },
        "diversity": {
            "active_sources": sum(1 for count in collected.values() if count > 0),
            "configured_sources": len(configured_sources),
            "publishing_sources": len(published_by_source),
            "top_collected": top(collected),
            "top_published": top(published_by_source),
        },
        "health": {
            "by_status": {status.value: sum(1 for entry in health if entry.status is status) for status in HealthStatus},
            "never_collected": len(set(configured_sources) - seen),
            "recent_errors": errors,
        },
        "freshness": {
            "items": len(ages),
            "median_hours": round(median(ages), 1) if ages else None,
            "p90_hours": round(_percentile(ages, 0.9), 1) if ages else None,
            "within_24h": round(sum(1 for age in ages if age <= FRESH_HOURS) / len(ages), 4) if ages else None,
        },
        "selection": {
            "runs_with_data": len(with_stats),
            "runs_without_data": len(runs) - len(with_stats),
            "fetched": sum(run.fetched_count for run in with_stats) if with_stats else None,
            "url_merged": sum(run.url_merged_count or 0 for run in with_stats) if with_stats else None,
            "topic_merged": sum(run.topic_merged_count or 0 for run in with_stats) if with_stats else None,
            "above_threshold": sum(run.above_threshold_count or 0 for run in with_stats) if with_stats else None,
            "per_run": [
                {
                    "run_id": run.id,
                    "started_at": run.started_at,
                    "fetched": run.fetched_count,
                    "selected": run.selected_count,
                    "url_merged": run.url_merged_count,
                    "topic_merged": run.topic_merged_count,
                    "above_threshold": run.above_threshold_count,
                }
                for run in runs
            ],
        },
        "filtering": _filtering(evaluation),
        "reliability": {
            "labels": {label.value: labels.get(label.value, 0) for label in ReliabilityLabel},
            "unlabeled": labels.get("none", 0),
            "unanalyzed": unanalyzed,
        },
    }


def _filtering(report: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Summary of the hand evaluation (lot 11), or None where it is not available."""
    if report is None:
        return None
    selection = report.get("selection") or {}
    reliability = report.get("reliability") or {}
    return {
        "annotated": report.get("annotated", 0),
        "compared": report.get("compared", 0),
        "small_sample": bool(report.get("small_sample", True)),
        "precision": selection.get("precision"),
        "recall": selection.get("recall"),
        "false_reliable": reliability.get("false_reliable"),
        "min_sample": MIN_RELIABLE_SAMPLE,
    }
