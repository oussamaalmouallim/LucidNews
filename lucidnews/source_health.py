"""Per-source health: stable source keys, per-run outcomes and health status.

A *source key* identifies one configured sub-source, e.g. ``rss/LWN.net``,
``github/vllm-project/vllm``, ``github/@torvalds``, ``reddit/r/devops`` or
``hackernews``. Each run records one outcome per key in the archive; the health
report aggregates those outcomes over a time window.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from .models import Config, ContentItem, SourceType

# Display names used by the orchestrator for each scraper.
SCRAPER_SOURCE_TYPES: Dict[str, str] = {
    "GitHub": SourceType.GITHUB.value,
    "Hacker News": SourceType.HACKERNEWS.value,
    "RSS Feeds": SourceType.RSS.value,
    "Reddit": SourceType.REDDIT.value,
    "Telegram": SourceType.TELEGRAM.value,
    "Twitter": SourceType.TWITTER.value,
    "OSS Insight": SourceType.OSSINSIGHT.value,
    "GDELT": SourceType.GDELT.value,
    "Google News": SourceType.GOOGLE_NEWS.value,
}


def rss_key(name: str) -> str:
    return f"rss/{name}"


def github_repo_key(owner: str, repo: str) -> str:
    return f"github/{owner}/{repo}"


def github_user_key(username: str) -> str:
    return f"github/@{username}"


def source_key(item: ContentItem) -> str:
    """Key of the configured sub-source that produced an item."""
    meta = item.metadata
    source_type = item.source_type
    if source_type is SourceType.RSS and meta.get("feed_name"):
        return rss_key(meta["feed_name"])
    if source_type is SourceType.GITHUB:
        if meta.get("event_type") and item.author:
            return github_user_key(item.author)
        if meta.get("repo"):
            owner, _, repo = str(meta["repo"]).partition("/")
            return github_repo_key(owner, repo)
    if source_type is SourceType.REDDIT and meta.get("subreddit"):
        return f"reddit/r/{meta['subreddit']}"
    if source_type is SourceType.TELEGRAM and meta.get("channel"):
        return f"telegram/@{meta['channel']}"
    return source_type.value


def configured_source_keys(config: Config) -> Dict[str, str]:
    """Enabled sub-sources as {source key: source type}."""
    sources = config.sources
    keys: Dict[str, str] = {}
    for feed in sources.rss:
        if feed.enabled:
            keys[rss_key(feed.name)] = SourceType.RSS.value
    for page in sources.pages:  # a list page is read as a feed and keyed like one
        if page.enabled:
            keys[rss_key(page.name)] = SourceType.RSS.value
    for entry in sources.github:
        if not entry.enabled:
            continue
        if entry.type == "repo_releases" and entry.owner and entry.repo:
            keys[github_repo_key(entry.owner, entry.repo)] = SourceType.GITHUB.value
        elif entry.type == "user_events" and entry.username:
            keys[github_user_key(entry.username)] = SourceType.GITHUB.value
    if sources.hackernews.enabled:
        keys[SourceType.HACKERNEWS.value] = SourceType.HACKERNEWS.value
    if sources.reddit.enabled:
        for subreddit in sources.reddit.subreddits:
            if subreddit.enabled:
                keys[f"reddit/r/{subreddit.subreddit}"] = SourceType.REDDIT.value
    if sources.telegram.enabled:
        for channel in sources.telegram.channels:
            if channel.enabled:
                keys[f"telegram/@{channel.channel}"] = SourceType.TELEGRAM.value
    for name in ("twitter", "ossinsight", "gdelt", "google_news"):
        section = getattr(sources, name)
        if section is not None and section.enabled:
            keys[name] = name
    return keys


@dataclass(frozen=True)
class SourceRunOutcome:
    """One source's result in one run."""

    source_key: str
    source_type: str
    status: str  # success | empty | failure
    fetched_count: int = 0
    selected_count: int = 0
    error: Optional[str] = None


def build_source_outcomes(
    configured: Mapping[str, str],
    fetched_items: Iterable[ContentItem],
    selected_items: Iterable[ContentItem],
    source_errors: Mapping[str, str],
    failed_types: Mapping[str, str],
) -> List[SourceRunOutcome]:
    """Combine configuration, fetch results and errors into one outcome per source.

    ``source_errors`` holds per-sub-source errors reported by scrapers;
    ``failed_types`` holds whole-scraper failures by source type.
    """
    fetched: Dict[str, int] = {}
    types = dict(configured)
    for item in fetched_items:
        key = item.metadata.get("source_key") or source_key(item)
        fetched[key] = fetched.get(key, 0) + 1
        types.setdefault(key, item.source_type.value)
    selected: Dict[str, int] = {}
    for item in selected_items:
        key = item.metadata.get("source_key") or source_key(item)
        selected[key] = selected.get(key, 0) + 1
    for key in source_errors:
        types.setdefault(key, key.split("/", 1)[0])

    outcomes = []
    for key in sorted(types):
        source_type = types[key]
        error = source_errors.get(key) or failed_types.get(source_type)
        count = fetched.get(key, 0)
        if error and count == 0:
            status = "failure"
        elif count:
            status = "success"
        else:
            status = "empty"
        outcomes.append(
            SourceRunOutcome(
                source_key=key,
                source_type=source_type,
                status=status,
                fetched_count=count,
                selected_count=selected.get(key, 0),
                error=error if status == "failure" else None,
            )
        )
    return outcomes


class HealthStatus(str, Enum):
    DEAD = "dead"  # failed the last DEAD_AFTER_FAILURES runs in a row
    FAILING = "failing"  # fails at least half of its runs
    SILENT = "silent"  # reachable but published nothing for a while
    NOISY = "noisy"  # many items, almost none worth selecting
    HEALTHY = "healthy"


SEVERITY = [HealthStatus.DEAD, HealthStatus.FAILING, HealthStatus.SILENT, HealthStatus.NOISY, HealthStatus.HEALTHY]

DEAD_AFTER_FAILURES = 3
FAILING_RATE = 0.5
SILENT_AFTER_RUNS = 5
NOISY_MIN_ITEMS = 30
NOISY_MAX_SELECTION_RATE = 0.02


@dataclass
class SourceHealth:
    source_key: str
    source_type: str
    runs: int = 0
    failures: int = 0
    empty_runs: int = 0
    items: int = 0
    selected: int = 0
    consecutive_failures: int = 0
    last_success_at: Optional[str] = None
    last_error: Optional[str] = None
    status: HealthStatus = HealthStatus.HEALTHY
    reasons: List[str] = field(default_factory=list)

    @property
    def failure_rate(self) -> float:
        return self.failures / self.runs if self.runs else 0.0

    @property
    def selection_rate(self) -> float:
        return self.selected / self.items if self.items else 0.0

    @property
    def items_per_run(self) -> float:
        return self.items / self.runs if self.runs else 0.0


def assess_health(rows: Sequence[Mapping[str, object]]) -> List[SourceHealth]:
    """Aggregate archived outcomes (newest first) into per-source health, worst first.

    Each row needs: source_key, source_type, status, fetched_count, selected_count,
    error, started_at.
    """
    by_key: Dict[str, SourceHealth] = {}
    streak_open: Dict[str, bool] = {}
    for row in rows:
        key = str(row["source_key"])
        health = by_key.get(key)
        if health is None:
            health = by_key[key] = SourceHealth(key, str(row["source_type"]))
            streak_open[key] = True
        status = row["status"]
        health.runs += 1
        health.items += int(row["fetched_count"] or 0)
        health.selected += int(row["selected_count"] or 0)
        if status == "failure":
            health.failures += 1
            health.last_error = health.last_error or (str(row["error"]) if row["error"] else None)
            if streak_open[key]:
                health.consecutive_failures += 1
        else:
            streak_open[key] = False
            if status == "empty":
                health.empty_runs += 1
            elif health.last_success_at is None:
                health.last_success_at = str(row["started_at"])

    for health in by_key.values():
        if health.consecutive_failures >= DEAD_AFTER_FAILURES:
            health.status = HealthStatus.DEAD
            health.reasons.append(f"failed the last {health.consecutive_failures} runs")
        elif health.failure_rate >= FAILING_RATE:
            health.status = HealthStatus.FAILING
            health.reasons.append(f"failed {health.failures}/{health.runs} runs")
        elif health.runs >= SILENT_AFTER_RUNS and health.items == 0:
            health.status = HealthStatus.SILENT
            health.reasons.append(f"no items in {health.runs} runs")
        elif health.items >= NOISY_MIN_ITEMS and health.selection_rate < NOISY_MAX_SELECTION_RATE:
            health.status = HealthStatus.NOISY
            health.reasons.append(f"{health.selected}/{health.items} items selected")
    return sorted(
        by_key.values(),
        key=lambda h: (SEVERITY.index(h.status), -h.failure_rate, h.source_key),
    )


def health_to_dict(health: SourceHealth) -> Dict[str, object]:
    """JSON-ready view shared by ``lucidnews-sources --json`` and the web API."""
    return {
        "source": health.source_key,
        "type": health.source_type,
        "status": health.status.value,
        "reasons": health.reasons,
        "runs": health.runs,
        "failures": health.failures,
        "consecutive_failures": health.consecutive_failures,
        "empty_runs": health.empty_runs,
        "items": health.items,
        "selected": health.selected,
        "selection_rate": round(health.selection_rate, 4),
        "last_success_at": health.last_success_at,
        "last_error": health.last_error,
    }
