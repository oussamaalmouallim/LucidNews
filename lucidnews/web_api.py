"""Read-only HTTP API over the run archive (``lucidnews-api``), used by the web frontend.

Endpoints (JSON, GET only):

- ``/api/editions?limit=30``: recent runs that published a digest (up to 2000).
- ``/api/editions/period?since=&until=&lang=``: the news of every edition started in a period
  (ISO instants), deduplicated, best 100 listed.
- ``/api/editions/latest?lang=fr``: the latest edition in one language.
- ``/api/editions/<run_id>?lang=fr``: one edition. Each unanalyzed item carries
  ``source_domain``: the usual domain of its source, so the web app can file it by domain.
- ``/api/items/<item_id>?lang=fr``: one item with its reliability details and editions.
- ``/api/sources?days=14``: source health (configured sources) and per-run volumes.
- ``/api/coverage?days=14``: coverage of the 12 categories by the sources (archive).
- ``/api/search?q=&category=&source=&label=&limit=&offset=``: full-text search of the archive (FTS5).
- ``/api/sources/domains?days=90``: domain of each configured source (archive, else catalog).
- ``/api/catalog?category=ai``: recommended sources absent from the configuration.
- ``/api/quality/overview?days=14``: indicators of the watch (coverage, diversity, health,
  freshness, duplicates, reliability; hand evaluation summary on the local API only).

Subscriber preferences (local only, see ``subscribers_api``):

- ``GET /api/preferences/options``, ``GET /api/subscribers``
- ``GET /api/subscribers/<id>/preview`` (the newsletter as it would be sent)
- ``GET /api/deliveries``, ``GET /api/subscribers/<id>/deliveries`` (delivery log)
- ``POST /api/subscribers/<id>/confirmation`` (send the confirmation link again)
- ``POST /api/subscribers``, ``PUT /api/subscribers/<id>``, ``DELETE /api/subscribers/<id>``

Quality evaluation (local only, see ``evaluation``):

- ``GET /api/eval/items`` (blind candidates), ``GET /api/eval/report``
- ``PUT /api/eval/annotations/<item_id>``, ``DELETE /api/eval/annotations/<item_id>``

Settings and sources (local only, see ``settings_api`` and ``sources_api``):

- ``GET /api/settings``, ``PUT /api/settings``; ``GET /api/secrets`` only says which API key
  variables are set (keys are never entered or returned through the API)
- ``GET|POST /api/sources/config``, ``PUT|DELETE /api/sources/config/<key>``,
  ``POST /api/sources/test``
- ``GET|POST /api/runs`` (history, start a run), ``GET /api/runs/current``,
  ``GET|PUT /api/schedule`` (see ``runs_api``)

The server binds to localhost by default and never writes to the archive.

Who may use the routes above depends on ``auth.enabled``:

- accounts off (single operator): the subscriber, quality, settings, sources and run routes
  exist only on a loopback bind, accept only localhost Host headers (DNS rebinding) and, for
  writes, a JSON body from a localhost Origin (cross-site requests);
- accounts on: every route needs a session. A reader reaches only ``READER_ROUTES`` (the
  published news); everything else, including any route added later, is for administrators.
  Those routes no longer depend on the bind address, so they work behind a reverse proxy;
  writes need a JSON body from this site's Origin.
"""

import argparse
from collections import Counter
import ipaddress
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlsplit

from ._cli import add_data_dir_arguments
from .auth import AuthService, build_auth_service
from .auth.service import AuthRequest, AuthResult, RateLimiter
from .archive import ItemArchive, RunRecord
from .archive.search import CANDIDATE_CAP, SearchQueryError, search_terms
from .coverage import CoverageThresholds, compute_coverage
from .evaluation import AnnotationStore
from .evaluation.service import EvaluationService
from .i18n import DEFAULT_LANGUAGE, is_supported
from .models import Config, ContentItem, DigestConfig
from .processing import ProfileRegistry
from .quality_overview import quality_overview
from .source_domains import source_domains
from .runs_api import RunService, ScheduleService
from .reliability import ReliabilityLabel, SourceTier
from .reliability.assess import ReliabilityPolicy
from .source_health import assess_health, configured_source_keys, health_to_dict
from .source_quality import DEFAULT_DAYS, compute_source_quality, item_source_key, quality_to_dict
from .storage.manager import StorageManager
from .settings_api import SettingsService
from .source_catalog import CatalogEntry, load_catalog, recommendations
from .sources_api import SourcesService
from .newsletter.mailer import build_mailer
from .newsletter.preview import PreviewService
from .subscribers_api import SubscriberService
from .taxonomy import Category, importance_from_score

RUN_ID = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
ITEM_ID = re.compile(r"^[^\x00-\x1f\x7f]{1,300}$")
SUBSCRIBER_ID = re.compile(r"^[0-9a-f]{16}$")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
MAX_BODY_BYTES = 64 * 1024
LOCAL_ONLY = {"error": "only available when the API is bound to localhost"}
LOCAL_PREFIXES = (
    "/api/subscribers",
    "/api/deliveries",
    "/api/preferences",
    "/api/eval",
    "/api/settings",
    "/api/secrets",
    "/api/sources/config",
    "/api/sources/test",
    "/api/runs",
    "/api/schedule",
)
SOURCE_KEY = re.compile(r"^[^\x00-\x1f\x7f]{1,200}$")
# What a reader (an account without the admin role) may call: the published news, read-only.
# Deny by default: a route missing from this list is for administrators.
READER_ROUTES = re.compile(r"^/api/(health|search|editions(/.+)?|items/.+)$")
ADMIN_ONLY = {"error": "administrators only", "code": "admin_only"}
# Routes whose answer costs a scan of the archive: a fifth of the general rate.
HEAVY_ROUTES = ("/api/search", "/api/editions/period")
# Every answer is JSON: nothing in it may run, embed or be framed.
SECURITY_HEADERS = (
    ("X-Content-Type-Options", "nosniff"),
    ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
)


def client_ip(peer: str, forwarded_for: Optional[str], trusted: frozenset) -> str:
    """The client's address. X-Forwarded-For is read only from a trusted proxy, right to left,
    skipping the trusted hops: the first other address is the one that reached the proxy."""
    if peer not in trusted or not forwarded_for:
        return peer
    hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    for hop in reversed(hops):
        try:
            address = str(ipaddress.ip_address(hop))
        except ValueError:
            return peer  # a malformed chain: fall back to the proxy itself
        if address not in trusted:
            return address
    return peer


def reader_may(method: str, path: str) -> bool:
    return method == "GET" and READER_ROUTES.match(path.rstrip("/")) is not None


@dataclass
class ApiContext:
    archive: ItemArchive
    profile_names: Dict[str, Dict[str, str]] = field(default_factory=dict)
    profile_order: List[str] = field(default_factory=list)
    default_language: str = DEFAULT_LANGUAGE
    # source key -> type, for the sources still in the config (empty = show all)
    configured_sources: Dict[str, str] = field(default_factory=dict)
    # None when the API is not bound to loopback: subscriber routes are then refused.
    subscribers: Optional[SubscriberService] = None
    previews: Optional[PreviewService] = None
    evaluation: Optional[EvaluationService] = None
    # Source quality as the pipeline computes it (current registry, same window).
    reliability_policy: Optional[ReliabilityPolicy] = None
    source_quality_days: int = DEFAULT_DAYS
    # Domain of each source for unanalyzed items, computed once per new run: (run id, domains).
    source_domain_cache: tuple = (None, {})
    # Who the client is behind a reverse proxy, and how often it may call (``server`` in the config).
    trusted_proxies: frozenset = frozenset()
    limiter: Optional[RateLimiter] = None
    heavy_limiter: Optional[RateLimiter] = None
    # Settings, API keys and sources (local only, like subscribers).
    settings: Optional[SettingsService] = None
    sources: Optional[SourcesService] = None
    # The loaded configuration (watched categories, configured sources for the catalog).
    config: Optional[Config] = None
    catalog: List[CatalogEntry] = field(default_factory=list)
    # Start a run and schedule it (local only).
    runs: Optional[RunService] = None
    schedule: Optional[ScheduleService] = None
    # None: accounts are off (auth.enabled) and every route stays open, as before.
    auth: Optional[AuthService] = None


def _profile_id(item: ContentItem) -> str:
    if item.processing:
        return item.processing.classification.profile
    return item.profile if isinstance(item.profile, str) else "unclassified"


def _profile_name(ctx: ApiContext, profile_id: str, language: str) -> str:
    names = ctx.profile_names.get(profile_id, {})
    return names.get(language, names.get("default", profile_id.replace("-", " ").title()))


def item_payload(item: ContentItem, language: str) -> Dict[str, Any]:
    processing = item.processing
    analysis = processing.analysis if processing else None
    artifact = processing.artifacts.get(language) if processing else None
    reliability = processing.reliability if processing else None

    primary = next((block for block in artifact.blocks if block.primary), None) if artifact else None
    score = analysis.score if analysis else None
    importance = importance_from_score(score)
    return {
        "id": item.id,
        "title": artifact.title if artifact else item.title,
        "url": str(item.url),
        "score": score,
        "importance": importance.value if importance else None,
        "categories": list(analysis.categories) if analysis else [],
        "tags": list(analysis.tags) if analysis else [],
        "summary": primary.content if primary else (analysis.summary if analysis else ""),
        "sections": [
            {"id": block.id, "title": block.title, "content": block.content}
            for block in (artifact.blocks if artifact else [])
            if not block.primary
        ],
        "reliability": reliability.model_dump(mode="json") if reliability else None,
        "source_type": item.source_type.value,
        "author": item.author,
        "published_at": item.published_at.isoformat(),
        "discussion_url": item.metadata.get("discussion_url"),
        "translated": artifact is not None,
        # Left unanalyzed because the AI quota ran out: original headline, no AI content.
        "ai_skipped": bool(processing and processing.ai_skipped),
    }


def item_detail_payload(ctx: "ApiContext", item: ContentItem, language: str) -> Dict[str, Any]:
    processing = item.processing
    analysis = processing.analysis if processing else None
    claim = analysis.claim if analysis else None
    return {
        **item_payload(item, language),
        "language": language,
        "available_languages": sorted(processing.artifacts) if processing else [],
        "profile": _profile_id(item),
        "profile_name": _profile_name(ctx, _profile_id(item), language),
        # The claim evidence comes from the AI analysis, which is written in English.
        "claim": {"status": claim.status.value, "evidence": claim.evidence} if claim else None,
        "editions": [run_payload(run) for run in ctx.archive.runs_selecting(item.id)],
    }


def run_payload(run: RunRecord) -> Dict[str, Any]:
    return {
        "id": run.id,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "fetched_count": run.fetched_count,
        "selected_count": run.selected_count,
        "ai_limit": run.ai_limit,
        "tokens_used": run.tokens_used,
        "ai_skipped_count": run.ai_skipped_count,
    }


def run_history_payload(run: RunRecord) -> Dict[str, Any]:
    """Every run, published or not, with its status (failed, empty...) and error."""
    return {**run_payload(run), "status": run.status, "error": run.error, "unscored_count": run.unscored_count}


def list_editions(ctx: ApiContext, limit: int = 30) -> Dict[str, Any]:
    runs = [
        run
        for run in ctx.archive.list_runs(limit=limit * 3)
        if run.status == "success" and run.selected_count > 0
    ]
    return {"editions": [run_payload(run) for run in runs[:limit]]}


SOURCE_DOMAIN_DAYS = 90


def _source_domain_of(ctx: ApiContext, items: List[ContentItem]) -> Dict[str, Optional[str]]:
    """The usual domain of each item's source (AI history of the source, else the catalog).

    Used to place news the AI did not analyze in a domain section. It describes the source, not
    the news: the interface says so."""
    if not items:
        return {}
    latest = ctx.archive.list_runs(limit=1)
    marker = latest[0].id if latest else None
    cached_marker, domains = ctx.source_domain_cache
    keys = {item_source_key(item) for item in items}
    if cached_marker != marker or not keys <= domains.keys():
        if cached_marker != marker:
            domains = {}
        history = ctx.archive.items_between(datetime.now(timezone.utc) - timedelta(days=SOURCE_DOMAIN_DAYS))
        domains = {**domains, **{key: value["category"] for key, value in source_domains(history, ctx.catalog, keys).items()}}
        ctx.source_domain_cache = (marker, domains)
    return {item.id: domains.get(item_source_key(item)) for item in items}


def _sections_payload(ctx: ApiContext, selected: List[ContentItem], language: str) -> Dict[str, Any]:
    """Sections and unanalyzed items of an edition, or of a period."""
    items = [item for item in selected if not (item.processing and item.processing.ai_skipped)]
    # Same order as the digest: best-known publishers first, then most recent.
    tier_rank = {tier: rank for rank, tier in enumerate(SourceTier)}
    unanalyzed = sorted(
        (item for item in selected if item.processing and item.processing.ai_skipped),
        key=lambda item: (
            tier_rank[item.processing.reliability.source_tier]
            if item.processing.reliability
            else len(tier_rank),
            -item.published_at.timestamp(),
        ),
    )
    items.sort(
        key=lambda item: (
            -(item.processing.analysis.score or 0)
            if item.processing and item.processing.analysis
            else 0,
            -item.published_at.timestamp(),
        )
    )
    analyzed_total = len(items)

    groups: Dict[str, List[ContentItem]] = {}
    for item in items:
        groups.setdefault(_profile_id(item), []).append(item)
    order = {profile_id: index for index, profile_id in enumerate(ctx.profile_order)}
    ordered = sorted(groups.items(), key=lambda group: order.get(group[0], len(order)))

    languages = sorted(
        {lang for item in items if item.processing for lang in item.processing.artifacts}
    )
    domain_of = _source_domain_of(ctx, unanalyzed)
    return {
        "analyzed_total": analyzed_total,
        "language": language,
        "available_languages": languages,
        "sections": [
            {
                "profile": profile_id,
                "name": _profile_name(ctx, profile_id, language),
                "items": [item_payload(item, language) for item in group_items],
            }
            for profile_id, group_items in ordered
        ],
        "unanalyzed": [{**item_payload(item, language), "source_domain": domain_of[item.id]} for item in unanalyzed],
    }


def edition_payload(ctx: ApiContext, run: RunRecord, language: str) -> Dict[str, Any]:
    selected = list(ctx.archive.get_items(ctx.archive.run_item_ids(run.id, selected_only=True)).values())
    body = _sections_payload(ctx, selected, language)
    body.pop("analyzed_total")
    return {**run_payload(run), **body}


MAX_PERIOD_DAYS = 3700
MAX_EDITIONS_LIMIT = 2000


def _instant(value: Optional[str]) -> Optional[datetime]:
    """An ISO 8601 instant (``Z`` accepted) as an aware UTC datetime, or None if invalid."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def period_payload(ctx: ApiContext, since: datetime, until: datetime, language: str) -> Dict[str, Any]:
    """The news of every published edition started in [since, until), best score first.

    An item published by several editions appears once. Every item is listed, best score first.
    """
    runs = [
        run
        for run in ctx.archive.list_runs(limit=MAX_EDITIONS_LIMIT)
        if run.status == "success"
        and run.selected_count > 0
        and since <= _instant(run.started_at) < until  # type: ignore[operator]
    ]
    ids: List[str] = []
    seen: set[str] = set()
    for run in runs:
        for item_id in ctx.archive.run_item_ids(run.id, selected_only=True):
            if item_id not in seen:
                seen.add(item_id)
                ids.append(item_id)
    selected = list(ctx.archive.get_items(ids).values())
    body = _sections_payload(ctx, selected, language)
    total = body.pop("analyzed_total")
    return {
        "id": "period",
        "started_at": since.isoformat(),
        "finished_at": until.isoformat(),
        "fetched_count": sum(run.fetched_count for run in runs),
        "selected_count": len(selected),
        "ai_limit": None,
        "tokens_used": 0,
        "ai_skipped_count": 0,
        "edition_count": len(runs),
        "analyzed_total": total,
        **body,
    }


MAX_HEALTH_DAYS = 90


def source_health_payload(ctx: ApiContext, days: int) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    report = assess_health(ctx.archive.source_run_rows(since))
    seen = {health.source_key for health in report}
    if ctx.configured_sources:
        report = [health for health in report if health.source_key in ctx.configured_sources]
    runs = [
        run
        for run in ctx.archive.list_runs(limit=500)
        if run.status != "running" and run.started_at >= since.isoformat()
    ]
    quality = (
        compute_source_quality(
            ctx.archive.items_between(datetime.now(timezone.utc) - timedelta(days=ctx.source_quality_days)),
            ctx.reliability_policy,
        )
        if ctx.source_quality_days
        else {}
    )
    return {
        "days": days,
        "quality_days": ctx.source_quality_days,
        "sources": [
            {**health_to_dict(health), "quality": quality_to_dict(quality.get(health.source_key))}
            for health in report
        ],
        "configured_without_history": sorted(set(ctx.configured_sources) - seen),
        "runs": [run_payload(run) for run in reversed(runs)],  # oldest first
    }


def coverage_payload(ctx: ApiContext, days: int) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    digest = ctx.config.digest if ctx.config is not None else DigestConfig()
    published = {item.id for item in ctx.archive.items_between(since, selected_only=True)}
    coverage = compute_coverage(
        ctx.archive.items_between(since),
        published,
        ctx.configured_sources,
        digest.watched_categories,
        CoverageThresholds(digest.coverage_min_sources, digest.coverage_min_items),
        ctx.reliability_policy,
    )
    return {
        "days": days,
        "watched": digest.watched_categories,
        "only_watched": digest.only_watched_categories,
        "min_sources": digest.coverage_min_sources,
        "min_items": digest.coverage_min_items,
        **coverage,
    }


def source_domains_payload(ctx: ApiContext, days: int) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    items = ctx.archive.items_between(since)
    # Every source the interface can list: configured (enabled or not), seen in the archive, or in the catalog.
    keys = set(ctx.configured_sources) | {item_source_key(item) for item in items} | {entry.key for entry in ctx.catalog}
    domains = source_domains(items, ctx.catalog, keys)
    return {"days": days, "domains": domains}


MAX_SEARCH_LIMIT = 100


def search_payload(ctx: ApiContext, query: Dict[str, List[str]], language: str) -> tuple[int, Dict[str, Any]]:
    """Full-text search: ``q`` (required), filters ``category``, ``source``, ``label``, paging."""

    def one(name: str) -> Optional[str]:
        values = query.get(name)
        return values[0] if values and values[0] != "" else None

    try:
        terms = search_terms(one("q") or "")
    except SearchQueryError as exc:
        return HTTPStatus.BAD_REQUEST, {"error": str(exc)}
    category, source, label = one("category"), one("source"), one("label")
    if category is not None and category not in {entry.value for entry in Category}:
        return HTTPStatus.BAD_REQUEST, {"error": "unknown category"}
    if label is not None and label not in {entry.value for entry in ReliabilityLabel}:
        return HTTPStatus.BAD_REQUEST, {"error": "unknown reliability label"}
    if source is not None and not SOURCE_KEY.match(source):
        return HTTPStatus.BAD_REQUEST, {"error": "invalid source"}
    try:
        limit = int(one("limit") or 30)
        offset = int(one("offset") or 0)
    except ValueError:
        return HTTPStatus.BAD_REQUEST, {"error": "limit and offset must be integers"}
    if not 1 <= limit <= MAX_SEARCH_LIMIT or offset < 0:
        return HTTPStatus.BAD_REQUEST, {"error": f"limit must be between 1 and {MAX_SEARCH_LIMIT}, offset 0 or more"}
    try:
        candidates = ctx.archive.search(terms, CANDIDATE_CAP)
    except RuntimeError as exc:
        return HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}

    # Counts for the filters, over everything the words match (before any filter).
    facets: Dict[str, Counter] = {"categories": Counter(), "labels": Counter(), "sources": Counter()}
    matched = []
    for item, _rank in candidates:
        processing = item.processing
        analysis = processing.analysis if processing else None
        categories = list(analysis.categories) if analysis else []
        reliability = processing.reliability.label.value if processing and processing.reliability else None
        key = item_source_key(item)
        facets["categories"].update(categories)
        if reliability:
            facets["labels"][reliability] += 1
        facets["sources"][key] += 1
        if (
            (category is None or category in categories)
            and (label is None or reliability == label)
            and (source is None or key == source)
        ):
            matched.append((item, key, reliability, categories))

    page = []
    for item, key, reliability, categories in matched[offset : offset + limit]:
        payload = item_payload(item, language)
        editions = ctx.archive.runs_selecting(item.id)
        page.append(
            {
                "id": item.id,
                "title": payload["title"],
                "summary": (payload["summary"] or "")[:320],
                "score": payload["score"],
                "reliability": reliability,
                "categories": categories,
                "source": key,
                "source_type": item.source_type.value,
                "published_at": item.published_at.isoformat(),
                "edition": editions[0].id if editions else None,  # None: analyzed but never published
                "edition_at": editions[0].started_at if editions else None,
                "unanalyzed": payload["score"] is None,
            }
        )
    return HTTPStatus.OK, {
        "query": " ".join(terms),
        "terms": terms,
        "total": len(matched),
        "offset": offset,
        "limit": limit,
        # The best CANDIDATE_CAP matches are considered: say so rather than imply completeness.
        "truncated": len(candidates) >= CANDIDATE_CAP,
        "results": page,
        "facets": {
            "categories": {name: count for name, count in facets["categories"].items()},
            "labels": dict(facets["labels"]),
            "sources": [{"source": name, "count": count} for name, count in facets["sources"].most_common(30)],
        },
    }


def catalog_payload(ctx: ApiContext, category: Optional[str]) -> Dict[str, Any]:
    entries = recommendations(ctx.catalog, ctx.config, category) if ctx.config is not None else [
        entry for entry in ctx.catalog if category is None or entry.category == category
    ]
    return {"entries": [entry.to_dict() for entry in entries]}


def _days(query: Dict[str, List[str]]) -> Optional[int]:
    try:
        days = int((query.get("days") or ["14"])[0])
    except ValueError:
        return None
    return days if 1 <= days <= MAX_HEALTH_DAYS else None


def resolve(ctx: ApiContext, path: str, query: Dict[str, List[str]]) -> tuple[int, Dict[str, Any]]:
    """Route a GET request to a JSON payload: (status, body)."""
    language = (query.get("lang") or [ctx.default_language])[0].lower()
    if not is_supported(language):
        return HTTPStatus.BAD_REQUEST, {"error": f"unsupported language: {language}"}

    path = path.rstrip("/")
    if path.startswith(("/api/settings", "/api/secrets")):
        if ctx.settings is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        if path == "/api/settings":
            return ctx.settings.get()
        if path == "/api/settings/backups":
            return ctx.settings.backups()
        if path == "/api/secrets":
            return ctx.settings.secrets()
        return HTTPStatus.NOT_FOUND, {"error": "not found"}
    if path == "/api/sources/config":
        if ctx.sources is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        return ctx.sources.list()
    if path.startswith(("/api/runs", "/api/schedule")):
        if ctx.runs is None or ctx.schedule is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        if path == "/api/runs":
            return HTTPStatus.OK, {"runs": [run_history_payload(run) for run in ctx.archive.list_runs(limit=20)]}
        if path == "/api/runs/current":
            return ctx.runs.current()
        if path == "/api/schedule":
            return ctx.schedule.get()
        return HTTPStatus.NOT_FOUND, {"error": "not found"}
    if path == "/api/health":
        return HTTPStatus.OK, {"status": "ok"}
    if path == "/api/editions":
        raw_limit = (query.get("limit") or ["30"])[0]
        if not raw_limit.isdigit() or not 1 <= int(raw_limit) <= MAX_EDITIONS_LIMIT:
            return HTTPStatus.BAD_REQUEST, {"error": f"limit must be an integer between 1 and {MAX_EDITIONS_LIMIT}"}
        return HTTPStatus.OK, list_editions(ctx, limit=int(raw_limit))
    if path == "/api/editions/period":
        since, until = _instant((query.get("since") or [None])[0]), _instant((query.get("until") or [None])[0])
        if since is None or until is None or until <= since:
            return HTTPStatus.BAD_REQUEST, {"error": "since and until must be ISO 8601 instants, until after since"}
        if (until - since).days > MAX_PERIOD_DAYS:
            return HTTPStatus.BAD_REQUEST, {"error": f"period longer than {MAX_PERIOD_DAYS} days"}
        return HTTPStatus.OK, period_payload(ctx, since, until, language)
    if path == "/api/search":
        return search_payload(ctx, query, language)
    if path == "/api/sources/domains":
        days = _days(query)
        if days is None:
            return HTTPStatus.BAD_REQUEST, {"error": f"days must be an integer between 1 and {MAX_HEALTH_DAYS}"}
        return HTTPStatus.OK, source_domains_payload(ctx, days)
    if path in ("/api/sources", "/api/coverage", "/api/quality/overview"):
        days = _days(query)
        if days is None:
            return HTTPStatus.BAD_REQUEST, {"error": f"days must be an integer between 1 and {MAX_HEALTH_DAYS}"}
        if path == "/api/quality/overview":
            return HTTPStatus.OK, quality_overview(
                ctx.archive,
                days=days,
                configured_sources=ctx.configured_sources,
                digest=ctx.config.digest if ctx.config is not None else DigestConfig(),
                policy=ctx.reliability_policy,
                # Annotations are local data: their summary only on the local API.
                evaluation=ctx.evaluation.report() if ctx.evaluation is not None else None,
            )
        if path == "/api/coverage":
            return HTTPStatus.OK, coverage_payload(ctx, days)
        return HTTPStatus.OK, source_health_payload(ctx, days)
    if path == "/api/catalog":
        category = (query.get("category") or [None])[0]
        if category is not None and category not in {entry.value for entry in Category}:
            return HTTPStatus.BAD_REQUEST, {"error": "unknown category"}
        return HTTPStatus.OK, catalog_payload(ctx, category)
    if path == "/api/preferences/options":
        if ctx.subscribers is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        return HTTPStatus.OK, ctx.subscribers.options()
    if path == "/api/subscribers":
        if ctx.subscribers is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        return ctx.subscribers.list()
    if path == "/api/deliveries" or (path.startswith("/api/subscribers/") and path.endswith("/deliveries")):
        if ctx.subscribers is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        raw = (query.get("limit") or ["50"])[0]
        if not raw.isdigit() or not 1 <= int(raw) <= 200:
            return HTTPStatus.BAD_REQUEST, {"error": "limit must be an integer between 1 and 200"}
        sub_id = None
        if path != "/api/deliveries":
            sub_id = path.removeprefix("/api/subscribers/").removesuffix("/deliveries")
            if not SUBSCRIBER_ID.match(sub_id):
                return HTTPStatus.BAD_REQUEST, {"error": "invalid subscriber id"}
        return ctx.subscribers.deliveries(sub_id, int(raw))
    if path.startswith("/api/subscribers/") and path.endswith("/preview"):
        if ctx.subscribers is None or ctx.previews is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        sub_id = path.removeprefix("/api/subscribers/").removesuffix("/preview")
        if not SUBSCRIBER_ID.match(sub_id):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid subscriber id"}
        subscriber = ctx.subscribers.get(sub_id)
        if subscriber is None:
            return HTTPStatus.NOT_FOUND, {"error": "subscriber not found"}
        return HTTPStatus.OK, ctx.previews.preview(subscriber)
    if path in ("/api/eval/items", "/api/eval/report"):
        if ctx.evaluation is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        if path == "/api/eval/items":
            return HTTPStatus.OK, ctx.evaluation.candidates()
        return HTTPStatus.OK, ctx.evaluation.report()
    if path.startswith("/api/items/"):
        item_id = unquote(path.removeprefix("/api/items/"))
        if not ITEM_ID.match(item_id):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid item id"}
        item = ctx.archive.get_item(item_id)
        # Unanalyzed items (AI quota) have a page too: the edition links to it.
        if item is None or not item.processing or not (item.processing.analysis or item.processing.ai_skipped):
            return HTTPStatus.NOT_FOUND, {"error": "item not found"}
        return HTTPStatus.OK, item_detail_payload(ctx, item, language)
    if path.startswith("/api/editions/"):
        key = path.removeprefix("/api/editions/")
        if key == "latest":
            run = ctx.archive.latest_published_run()
        elif RUN_ID.match(key):
            run = ctx.archive.get_run(key)
        else:
            return HTTPStatus.BAD_REQUEST, {"error": "invalid edition id"}
        if run is None:
            return HTTPStatus.NOT_FOUND, {"error": "edition not found"}
        return HTTPStatus.OK, edition_payload(ctx, run, language)
    return HTTPStatus.NOT_FOUND, {"error": "not found"}


def resolve_write(ctx: ApiContext, method: str, path: str, body: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
    """Route a POST/PUT/DELETE request (subscriber preferences and annotations)."""
    path = path.rstrip("/")
    if path.startswith(("/api/settings", "/api/secrets")):
        if ctx.settings is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        if path == "/api/settings" and method == "PUT":
            return ctx.settings.update(body)
        if path == "/api/settings/restore" and method == "POST":
            return ctx.settings.restore(body)
        return HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method not allowed"}
    if path.startswith(("/api/runs", "/api/schedule")):
        if ctx.runs is None or ctx.schedule is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        if path == "/api/runs" and method == "POST":
            return ctx.runs.start()
        if path == "/api/schedule" and method == "PUT":
            return ctx.schedule.update(body)
        return HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method not allowed"}
    if path.startswith(("/api/sources/config", "/api/sources/test")):
        if ctx.sources is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        if path == "/api/sources/test" and method == "POST":
            return ctx.sources.test(body)
        if path == "/api/sources/config" and method == "POST":
            return ctx.sources.add(body)
        if path.startswith("/api/sources/config/"):
            key = unquote(path.removeprefix("/api/sources/config/"))
            if not SOURCE_KEY.match(key):
                return HTTPStatus.BAD_REQUEST, {"error": "invalid source key"}
            if method == "PUT":
                return ctx.sources.update(key, body)
            if method == "DELETE":
                return ctx.sources.delete(key, body)
        return HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method not allowed"}
    if path.startswith("/api/eval/annotations/"):
        if ctx.evaluation is None:
            return HTTPStatus.FORBIDDEN, LOCAL_ONLY
        item_id = unquote(path.removeprefix("/api/eval/annotations/"))
        if not ITEM_ID.match(item_id):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid item id"}
        if method == "PUT":
            return ctx.evaluation.annotate(item_id, body)
        if method == "DELETE":
            return ctx.evaluation.unannotate(item_id)
        return HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method not allowed"}
    if ctx.subscribers is None:
        return HTTPStatus.FORBIDDEN, LOCAL_ONLY
    if path == "/api/subscribers" and method == "POST":
        return ctx.subscribers.create(body)
    if path.startswith("/api/subscribers/") and path.endswith("/confirmation"):
        sub_id = path.removeprefix("/api/subscribers/").removesuffix("/confirmation")
        if not SUBSCRIBER_ID.match(sub_id):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid subscriber id"}
        if method != "POST":
            return HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method not allowed"}
        return ctx.subscribers.resend_confirmation(sub_id)
    if path.startswith("/api/subscribers/"):
        sub_id = path.removeprefix("/api/subscribers/")
        if not SUBSCRIBER_ID.match(sub_id):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid subscriber id"}
        if method == "PUT":
            return ctx.subscribers.update(sub_id, body)
        if method == "DELETE":
            return ctx.subscribers.delete(sub_id)
    return HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method not allowed"}


def _hostname(value: str) -> str:
    """Host part of a Host header or Origin: ``[::1]:8765`` -> ``::1``."""
    value = value.strip().lower()
    if "//" in value:
        value = urlsplit(value).netloc
    if value.startswith("["):
        return value[1 : value.find("]")] if "]" in value else value
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


def is_local_request(host: Optional[str], origin: Optional[str]) -> bool:
    """Same-machine request: localhost Host (no DNS rebinding) and, if sent, localhost Origin."""
    if not host or _hostname(host) not in LOCAL_HOSTS:
        return False
    return origin is None or _hostname(origin) in LOCAL_HOSTS


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def make_handler(ctx: ApiContext) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "LucidNews"

        def version_string(self) -> str:
            return self.server_version  # no Python version in the Server header

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            # The request line without its query: an OAuth code or a search must not reach the logs.
            if args and isinstance(args[0], str) and "?" in args[0]:
                args = (args[0].split("?", 1)[0] + " " + args[0].rsplit(" ", 1)[-1], *args[1:])
            super().log_message(format, *args)

        def _client(self) -> str:
            return client_ip(self.client_address[0], self.headers.get("X-Forwarded-For"), ctx.trusted_proxies)

        def _within_rate(self, path: str) -> bool:
            """At most ``server.requests_per_minute`` calls a minute per client, a fifth on costly routes."""
            client = self._client()
            heavy = path.rstrip("/") in HEAVY_ROUTES
            if (ctx.limiter is None or ctx.limiter.hit(client)) and (not heavy or ctx.heavy_limiter is None or ctx.heavy_limiter.hit(client)):
                return True
            self._send(HTTPStatus.TOO_MANY_REQUESTS, {"error": "too many requests, try again in a minute", "code": "rate_limited"}, retry_after=60)
            return False

        def _security_headers(self) -> None:
            for name, value in SECURITY_HEADERS:
                self.send_header(name, value)

        def _send(self, status: int, body: Dict[str, Any], retry_after: Optional[int] = None) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self._security_headers()
            if retry_after:
                self.send_header("Retry-After", str(retry_after))
            self.end_headers()
            self.wfile.write(data)

        def _auth_route(self, method: str, parts, body: Dict[str, Any]) -> None:
            """``/api/auth/*``: reachable without a session, and from any host the app is served on."""
            if ctx.auth is None:
                if method == "GET" and parts.path.rstrip("/") == "/api/auth/session":
                    self._send(HTTPStatus.OK, {"enabled": False, "authenticated": False, "user": None, "signup_enabled": False, "providers": {"google": False}})
                else:
                    self._send(HTTPStatus.NOT_FOUND, {"error": "not found", "code": "not_found"})
                return
            request = AuthRequest(method, parts.path, parse_qs(parts.query), body, self.headers, self._client())
            try:
                result = ctx.auth.handle(request)
            except Exception as exc:  # never leak a traceback to the client
                self.log_error("auth request failed: %r", exc)
                result = AuthResult(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal error", "code": "internal"})
            data = json.dumps(result.body or {}, ensure_ascii=False).encode("utf-8")
            self.send_response(result.status)
            for cookie in result.cookies:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Cache-Control", "no-store")
            self._security_headers()
            if result.location:
                self.send_header("Location", result.location)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _allowed(self, method: str, path: str) -> bool:
            """Accounts on: a session, and the admin role outside ``READER_ROUTES``.
            Accounts off: the localhost checks (there is nobody to identify)."""
            if ctx.auth is None:
                local = is_local_request(self.headers.get("Host"), self.headers.get("Origin"))
                if not local and (method != "GET" or path.startswith(LOCAL_PREFIXES)):
                    self._send(HTTPStatus.FORBIDDEN, {"error": "local requests only"})
                    return False
                return True
            user = ctx.auth.current_user(self.headers)
            if user is None:
                self._send(HTTPStatus.UNAUTHORIZED, {"error": "authentication required", "code": "unauthenticated"})
                return False
            if not user.is_admin and not reader_may(method, path):
                self._send(HTTPStatus.FORBIDDEN, ADMIN_ONLY)
                return False
            if method != "GET" and not ctx.auth.same_origin(self.headers):
                self._send(HTTPStatus.FORBIDDEN, {"error": "cross-site request refused", "code": "forbidden"})
                return False
            return True

        def _guarded(self, handler) -> None:
            try:
                status, body = handler()
            except Exception as exc:  # never leak a traceback to the client
                self.log_error("request failed: %r", exc)
                status, body = HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal error"}
            self._send(status, body)

        def do_GET(self) -> None:  # noqa: N802 (stdlib name)
            parts = urlsplit(self.path)
            if not self._within_rate(parts.path):
                return
            if parts.path.rstrip("/").startswith("/api/auth"):
                self._auth_route("GET", parts, {})
                return
            if not self._allowed("GET", parts.path):
                return
            self._guarded(lambda: resolve(ctx, parts.path, parse_qs(parts.query)))

        def _write(self, method: str) -> None:
            parts = urlsplit(self.path)
            if not self._within_rate(parts.path):
                return
            is_auth = parts.path.rstrip("/").startswith("/api/auth")
            if not is_auth and not self._allowed(method, parts.path):
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body too large"})
                return
            body: Any = {}
            if length:
                # JSON only: a cross-site form post cannot send it without a CORS preflight.
                if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                    self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "expected application/json"})
                    return
                try:
                    body = json.loads(self.rfile.read(length))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
                    return
            if not isinstance(body, dict):
                self._send(HTTPStatus.BAD_REQUEST, {"error": "expected a JSON object"})
                return
            if is_auth:
                self._auth_route(method, parts, body)
                return
            self._guarded(lambda: resolve_write(ctx, method, parts.path, body))

        def do_POST(self) -> None:  # noqa: N802
            self._write("POST")

        def do_PUT(self) -> None:  # noqa: N802
            self._write("PUT")

        def do_DELETE(self) -> None:  # noqa: N802
            self._write("DELETE")

    return Handler


def build_context(data_dir: str, config_path: Optional[str], *, local_features: bool = False) -> ApiContext:
    """``local_features``: subscriber preferences, annotations, settings and runs (personal or
    editable data), enabled on a loopback bind. With accounts on they are always enabled:
    the admin role guards them instead of the bind address."""
    storage = StorageManager(data_dir=data_dir, config_path=config_path)
    config = storage.load_config()
    local_features = local_features or config.auth.enabled
    archive_path = Path(config.archive.path)
    if not archive_path.is_absolute():
        archive_path = Path(data_dir) / archive_path
    if not archive_path.exists():
        raise FileNotFoundError(f"No archive at {archive_path}. Run `uv run lucidnews` first.")
    profiles = ProfileRegistry.load(
        Path(config.processing.profiles_dir), config.processing.default_profile
    )
    archive = ItemArchive(archive_path)
    ctx = ApiContext(
        archive=archive,
        profile_names=profiles.names,
        profile_order=list(config.digest.profile_order),
        default_language=(config.ai.languages or [DEFAULT_LANGUAGE])[0],
        configured_sources=configured_source_keys(config),
        reliability_policy=ReliabilityPolicy.with_overrides(
            config.reliability.domains, config.reliability.accounts
        ),
        source_quality_days=config.digest.source_quality_days,
        config=config,
        catalog=load_catalog(),
        subscribers=(
            SubscriberService(
                storage.subscribers,
                config.ai.languages,
                configured_source_keys(config),
                weekly_day=config.email.weekly_day if config.email else 0,
                mailer=lambda: (
                    build_mailer(config.email, storage.subscribers)
                    if config.email and config.email.enabled
                    else None
                ),
            )
            if local_features
            else None
        ),
        previews=PreviewService(archive, config, profiles.names) if local_features else None,
        evaluation=(
            EvaluationService.from_config(
                config, archive, AnnotationStore(Path(data_dir) / "eval" / "annotations.json")
            )
            if local_features
            else None
        ),
    )
    if local_features:
        ctx.settings = SettingsService(
            config_path=storage.config_path,
            backup_dir=Path(data_dir) / "backups",
            profiles=profiles,
            on_change=lambda: _reload(ctx, data_dir, config_path),
        )
        ctx.sources = SourcesService(ctx.settings)
        settings = ctx.settings
        ctx.runs = RunService(Path(data_dir), config_path, secret_values=lambda: settings.secret_values())
        ctx.schedule = ScheduleService(Path(data_dir), config_path)
    ctx.auth = build_auth_service(config.auth, Path(data_dir))
    ctx.trusted_proxies = frozenset(config.server.trusted_proxies)
    ctx.limiter = RateLimiter(config.server.requests_per_minute, 60)
    ctx.heavy_limiter = RateLimiter(max(2, config.server.requests_per_minute // 5), 60)
    return ctx


def _reload(ctx: ApiContext, data_dir: str, config_path: Optional[str]) -> None:
    """Serve the configuration just written (profiles, sources, languages...)."""
    fresh = build_context(data_dir, config_path, local_features=True)
    settings = ctx.settings
    # The settings and sources services stay: they hold the lock and the callback.
    kept = ("settings", "sources", "runs", "schedule", "auth", "limiter", "heavy_limiter")  # they hold locks, a process, callbacks or sign-in state
    ctx.__dict__.update({key: value for key, value in fresh.__dict__.items() if key not in kept})
    if settings is not None and fresh.settings is not None:
        settings.profiles = fresh.settings.profiles


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="LucidNews web API (archive read-only, local preferences)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    add_data_dir_arguments(parser)
    args = parser.parse_args(argv)

    try:
        # Subscriber data is personal: only served on a loopback bind.
        ctx = build_context(args.data_dir, args.config, local_features=is_loopback(args.host))
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    server = ThreadingHTTPServer((args.host, args.port), make_handler(ctx))
    print(f"LucidNews API on http://{args.host}:{args.port}/api/editions/latest", file=sys.stderr)
    if ctx.subscribers is None:
        print("Preferences and evaluation disabled (not bound to localhost).", file=sys.stderr)
    if ctx.auth is not None and ctx.auth.db.count_admins() == 0:
        print("No administrator account yet: run `uv run lucidnews-users add EMAIL --admin`.", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
