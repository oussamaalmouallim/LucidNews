"""Sources editable from the web app (local API routes only).

Lists every source of ``config.sources`` with its real state, and adds, edits,
enables, disables and removes them through ``SettingsService.edit_raw``: the
raw file is edited (``${VARIABLE}`` placeholders stay), checked by ``Config``,
backed up and written atomically, with the same version check.

A *test* fetches one source with its scraper, without AI and without the
archive, and reports what came back. Every request it makes, redirects
included, must go to a public address.

Each entry carries the key the run archive uses for its health (see
``source_health``), so the web app can join both. X (Twitter) is read only: it
needs browser cookies or an Apify token that cannot be checked from here.
"""

import asyncio
import html
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import httpx
from pydantic import ValidationError

from .models import (
    Config,
    GDELTConfig,
    GitHubSourceConfig,
    GoogleNewsConfig,
    HackerNewsConfig,
    OSSInsightConfig,
    RedditConfig,
    RedditSubredditConfig,
    RedditUserConfig,
    RSSSourceConfig,
    TelegramChannelConfig,
    TelegramConfig,
)
from .scrapers.base import short_error
from .settings_api import Response, SettingsService
from .source_health import github_repo_key, github_user_key, rss_key
from .storage.manager import _ENV_VAR_PATTERN
from .url_security import UnsafeURLError, validate_public_http_url
from .sectors import DEFAULT_SECTOR

COLLECTOR_USER_AGENT = "Mozilla/5.0 (compatible; LucidNews/1.0; RSS reader)"
TEST_TIMEOUT_SECONDS = 45
TEST_LOOKBACK_DAYS = 7
TEST_SAMPLE_SIZE = 5

GITHUB_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
GITHUB_REPO = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
SUBREDDIT = re.compile(r"^[A-Za-z0-9_]{2,21}$")
REDDIT_USER = re.compile(r"^[A-Za-z0-9_-]{3,20}$")
TELEGRAM_CHANNEL = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
FREE_TEXT = re.compile(r"^[^\x00-\x1f\x7f]{1,200}$")
SHORT_TEXT = re.compile(r"^[^\x00-\x1f\x7f]{1,60}$")
LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z]{2,4})?$")
COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
GDELT_LANGUAGE = re.compile(r"^[a-z]{2,20}$")


# Fields ------------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSpec:
    type: str  # text | url | int | choice | list | repository
    pattern: Optional[re.Pattern] = None
    minimum: int = 0
    maximum: int = 0
    choices: Tuple[str, ...] = ()
    max_items: int = 0
    optional: bool = False  # empty text is stored as null
    strip: Tuple[str, ...] = ()  # prefixes people paste (r/, @, https://t.me/...)


def _text(pattern: re.Pattern, *, optional: bool = False, strip: Tuple[str, ...] = ()) -> FieldSpec:
    return FieldSpec("text", pattern=pattern, optional=optional, strip=strip)


def _int(minimum: int, maximum: int) -> FieldSpec:
    return FieldSpec("int", minimum=minimum, maximum=maximum)


@dataclass(frozen=True)
class Kind:
    id: str
    source_type: str
    path: Tuple[str, ...]  # under "sources": a list, or one object
    fields: Dict[str, FieldSpec]
    is_list: bool = False
    identity: Tuple[str, ...] = ()  # fields required to add one
    match: Dict[str, str] = field(default_factory=dict)  # raw fields that tell list kinds apart
    group: Optional[str] = None  # reddit / telegram: a switch that pauses all of them
    tracked: bool = True  # health is recorded under this entry's key
    readonly: bool = False
    is_group: bool = False


KINDS: Dict[str, Kind] = {
    kind.id: kind
    for kind in (
        Kind(
            "rss", "rss", ("rss",), is_list=True, identity=("name", "url"),
            fields={"name": _text(SHORT_TEXT), "url": FieldSpec("url")},
        ),
        Kind(
            "github_repo", "github", ("github",), is_list=True, identity=("repository",),
            match={"type": "repo_releases"}, fields={"repository": FieldSpec("repository")},
        ),
        Kind(
            "github_user", "github", ("github",), is_list=True, identity=("username",),
            match={"type": "user_events"},
            fields={"username": _text(GITHUB_LOGIN, strip=("https://github.com/", "github.com/", "@"))},
        ),
        Kind(
            "reddit_subreddit", "reddit", ("reddit", "subreddits"), is_list=True, identity=("subreddit",),
            group="reddit",
            fields={
                "subreddit": _text(SUBREDDIT, strip=("https://www.reddit.com/r/", "https://reddit.com/r/", "/r/", "r/")),
                "sort": FieldSpec("choice", choices=("hot", "new", "top", "rising")),
                "fetch_limit": _int(1, 100),
                "min_score": _int(0, 100000),
            },
        ),
        Kind(
            # Their items are counted under the subreddit they were posted in.
            "reddit_user", "reddit", ("reddit", "users"), is_list=True, identity=("username",),
            group="reddit", tracked=False,
            fields={
                "username": _text(REDDIT_USER, strip=("https://www.reddit.com/user/", "/u/", "u/")),
                "fetch_limit": _int(1, 100),
            },
        ),
        Kind(
            "telegram_channel", "telegram", ("telegram", "channels"), is_list=True, identity=("channel",),
            group="telegram",
            fields={
                "channel": _text(TELEGRAM_CHANNEL, strip=("https://t.me/s/", "https://t.me/", "t.me/", "@")),
                "fetch_limit": _int(1, 100),
            },
        ),
        Kind(
            "hackernews", "hackernews", ("hackernews",),
            fields={"fetch_top_stories": _int(1, 200), "min_score": _int(0, 10000)},
        ),
        Kind(
            "ossinsight", "ossinsight", ("ossinsight",),
            fields={
                "period": FieldSpec("choice", choices=("past_24_hours", "past_28_days")),
                "languages": FieldSpec("list", pattern=SHORT_TEXT, max_items=10),
                "keywords": FieldSpec("list", pattern=SHORT_TEXT, max_items=20),
                "min_stars": _int(0, 1_000_000),
                "max_items": _int(1, 100),
            },
        ),
        Kind(
            "gdelt", "gdelt", ("gdelt",),
            fields={
                "query": _text(FREE_TEXT),
                "max_records": _int(1, 250),
                "language": _text(GDELT_LANGUAGE, optional=True),
            },
        ),
        Kind(
            "google_news", "google_news", ("google_news",),
            fields={
                "query": _text(FREE_TEXT),
                "language": _text(LANGUAGE_CODE),
                "country": _text(COUNTRY_CODE),
                "max_results": _int(1, 100),
            },
        ),
        Kind("twitter", "twitter", ("twitter",), fields={}, readonly=True),
        Kind("reddit", "reddit", ("reddit",), fields={"fetch_comments": _int(0, 50)}, is_group=True),
        Kind("telegram", "telegram", ("telegram",), fields={}, is_group=True),
    )
}
SINGLE_LABELS = {
    "hackernews": "Hacker News",
    "ossinsight": "OSS Insight",
    "gdelt": "GDELT",
    "google_news": "Google News",
    "twitter": "X (Twitter)",
    "reddit": "Reddit",
    "telegram": "Telegram",
}


def _clean_value(spec: FieldSpec, value: Any) -> Tuple[Any, Optional[str]]:
    """Normalized value, or an error message (never echoing the value)."""
    if spec.type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            return None, "must be a whole number"
        if not spec.minimum <= value <= spec.maximum:
            return None, f"must be between {spec.minimum} and {spec.maximum}"
        return value, None
    if spec.type == "choice":
        if value not in spec.choices:
            return None, f"must be one of: {', '.join(spec.choices)}"
        return value, None
    if spec.type == "list":
        if not isinstance(value, list) or len(value) > spec.max_items:
            return None, f"must be a list of at most {spec.max_items} entries"
        if any(not isinstance(entry, str) for entry in value):
            return None, "entries must be text"
        cleaned = [entry.strip() for entry in value if entry.strip()]
        if any(not spec.pattern.match(entry) for entry in cleaned):  # type: ignore[union-attr]
            return None, "entries must be 1 to 60 characters"
        return list(dict.fromkeys(cleaned)), None
    if not isinstance(value, str):
        return None, "must be text"
    text = value.strip()
    if spec.type == "url":
        if len(text) > 2000:
            return None, "URL too long"
        return text, None  # checked against url_security by the caller
    if spec.type == "repository":
        path = re.sub(r"^(?:https?://)?(?:www\.)?github\.com/", "", text)
        parts = [part for part in path.removesuffix(".git").split("/") if part]
        if len(parts) != 2 or not GITHUB_LOGIN.match(parts[0]) or not GITHUB_REPO.match(parts[1]):
            return None, "expected owner/repository or a GitHub URL"
        return f"{parts[0]}/{parts[1]}", None
    for prefix in spec.strip:
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):]
            break
    text = text.strip().strip("/")
    if not text and spec.optional:
        return None, None
    if not spec.pattern.match(text):  # type: ignore[union-attr]
        return None, "invalid format"
    return text, None


def clean_values(kind: Kind, values: Any, *, adding: bool) -> Tuple[Dict[str, Any], Dict[str, str]]:
    if not isinstance(values, dict):
        return {}, {"values": "expected an object"}
    cleaned: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    for name, value in values.items():
        if name == "enabled":
            if not isinstance(value, bool):
                errors[name] = "must be true or false"
            else:
                cleaned[name] = value
            continue
        spec = kind.fields.get(name)
        if spec is None:
            errors[name] = "not editable"
            continue
        result, error = _clean_value(spec, value)
        if error:
            errors[name] = error
        else:
            cleaned[name] = result
    if adding:
        for name in kind.identity:
            if name not in cleaned and name not in errors:
                errors[name] = "required"
    return cleaned, errors


def _raw_fields(kind: Kind, cleaned: Dict[str, Any]) -> Dict[str, Any]:
    """Form values -> raw config fields."""
    raw = {name: value for name, value in cleaned.items() if name != "repository"}
    if "repository" in cleaned:
        raw["owner"], raw["repo"] = cleaned["repository"].split("/", 1)
    return raw


def _has_placeholder(value: Any) -> bool:
    return bool(_ENV_VAR_PATTERN.search(json.dumps(value)))


# Entries -----------------------------------------------------------------------------


@dataclass
class Entry:
    kind: Kind
    key: str
    label: str
    model: Any  # validated model (None for a section absent from the file)
    raw: Optional[Dict[str, Any]]
    index: Optional[int] = None

    @property
    def configured(self) -> bool:
        return self.raw is not None


def _container(sources: Dict[str, Any], path: Tuple[str, ...], create: bool = False) -> Any:
    """Node at ``path`` in the raw sources; ``create`` makes missing parents and the final list."""
    node: Any = sources
    for depth, name in enumerate(path):
        if not isinstance(node, dict):
            return None
        if node.get(name) is None:
            if not create:
                return None
            node[name] = [] if depth == len(path) - 1 else {}
        node = node[name]
    return node


def _model_list(config: Config, kind: Kind) -> List[Any]:
    node: Any = config.sources
    for name in kind.path:
        node = getattr(node, name)
    return list(node or [])


def _key_and_label(kind: Kind, model: Any) -> Optional[Tuple[str, str]]:
    if kind.id == "rss":
        return rss_key(model.name), model.name
    if kind.id == "github_repo":
        if model.type != "repo_releases" or not (model.owner and model.repo):
            return None
        return github_repo_key(model.owner, model.repo), f"{model.owner}/{model.repo}"
    if kind.id == "github_user":
        if model.type != "user_events" or not model.username:
            return None
        return github_user_key(model.username), f"@{model.username}"
    if kind.id == "reddit_subreddit":
        return f"reddit/r/{model.subreddit}", f"r/{model.subreddit}"
    if kind.id == "reddit_user":
        return f"reddit/u/{model.username}", f"u/{model.username}"
    if kind.id == "telegram_channel":
        return f"telegram/@{model.channel}", f"@{model.channel}"
    return None


def list_entries(raw: Dict[str, Any], config: Config) -> List[Entry]:
    raw_sources = raw.get("sources") if isinstance(raw.get("sources"), dict) else {}
    entries: List[Entry] = []
    for kind in KINDS.values():
        if kind.is_list:
            raw_list = _container(raw_sources, kind.path) or []
            for index, model in enumerate(_model_list(config, kind)):
                identity = _key_and_label(kind, model)
                if identity is None or index >= len(raw_list):
                    continue
                entries.append(Entry(kind, identity[0], identity[1], model, raw_list[index], index))
        else:
            model = getattr(config.sources, kind.path[0])
            raw_entry = _container(raw_sources, kind.path)
            entries.append(Entry(kind, kind.id, SINGLE_LABELS[kind.id], model, raw_entry))
    return entries


def _values(entry: Entry) -> Dict[str, Any]:
    """Editable values; a field set through ${VARIABLE} is shown as written, never expanded."""
    model = entry.model if entry.model is not None else _default_model(entry.kind)
    values: Dict[str, Any] = {}
    for name in entry.kind.fields:
        if name == "repository":
            values[name] = f"{model.owner}/{model.repo}"
            continue
        raw_value = (entry.raw or {}).get(name)
        if raw_value is not None and _has_placeholder(raw_value):
            values[name] = raw_value
        else:
            value = getattr(model, name)
            values[name] = str(value) if name == "url" else value
    return values


def _default_model(kind: Kind) -> Any:
    return {
        "hackernews": HackerNewsConfig,
        "ossinsight": OSSInsightConfig,
        "gdelt": GDELTConfig,
        "google_news": GoogleNewsConfig,
        "reddit": RedditConfig,
        "telegram": TelegramConfig,
    }[kind.id]()


def _enabled(entry: Entry) -> bool:
    if entry.model is None:
        return False
    return bool(entry.model.enabled)


def _twitter_summary(entry: Entry) -> Optional[Dict[str, Any]]:
    if entry.model is None:
        return None
    model = entry.model
    return {"mode": model.mode, "users": len(model.users), "keywords": len(model.keywords)}


def _locked(entry: Entry) -> bool:
    if entry.raw is None:
        return False
    fields = set(entry.kind.fields) | ({"owner", "repo"} if entry.kind.id == "github_repo" else set())
    return any(_has_placeholder(entry.raw.get(name)) for name in fields)


def _validation_fields(kind: Kind, exc: ValidationError) -> Response:
    fields: Dict[str, str] = {}
    for error in exc.errors(include_url=False, include_input=False):
        names = [str(part) for part in error["loc"]]
        name = next((part for part in reversed(names) if part in kind.fields or part == "enabled"), None)
        if name is None and kind.id == "github_repo" and {"owner", "repo"} & set(names):
            name = "repository"
        fields.setdefault(name or "values", error["msg"].removeprefix("Value error, "))
    return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid source", "fields": fields}


# Service -----------------------------------------------------------------------------


@dataclass
class SourcesService:
    settings: SettingsService
    # Async check that a URL is public; replaced in tests (no DNS).
    resolve_public: Callable[[str], Awaitable[str]] = validate_public_http_url

    def list(self) -> Response:
        raw, version, config = self.settings.snapshot()
        entries = list_entries(raw, config)
        groups = {entry.kind.id: _enabled(entry) for entry in entries if entry.kind.is_group}
        return HTTPStatus.OK, {
            "version": version,
            "time_window_hours": config.collection.time_window_hours,
            "sources": [
                {
                    "key": entry.key,
                    "kind": entry.kind.id,
                    "type": entry.kind.source_type,
                    "label": entry.label,
                    "configured": entry.configured,
                    "enabled": _enabled(entry),
                    # False when the Reddit or Telegram switch pauses this source.
                    "group_enabled": groups.get(entry.kind.group, True) if entry.kind.group else None,
                    "values": _values(entry) if not entry.kind.readonly else {},
                    "summary": _twitter_summary(entry) if entry.kind.id == "twitter" else None,
                    "locked": _locked(entry),
                    "readonly": entry.kind.readonly,
                    "removable": entry.kind.is_list,
                    "tracked": entry.kind.tracked and not entry.kind.is_group,
                    "group": entry.kind.is_group,
                }
                for entry in entries
            ],
            "kinds": [
                {"id": kind.id, "type": kind.source_type, "fields": list(kind.fields), "identity": list(kind.identity)}
                for kind in KINDS.values()
                if kind.is_list
            ],
        }

    # Writes ------------------------------------------------------------------------

    def _check_url(self, cleaned: Dict[str, Any]) -> Optional[Dict[str, str]]:
        url = cleaned.get("url")
        if url is None:
            return None
        if _ENV_VAR_PATTERN.search(url):
            return {"url": "a ${VARIABLE} can only be written in config.json"}
        try:
            asyncio.run(self.resolve_public(url))
        except UnsafeURLError as exc:
            return {"url": str(exc)}
        return None

    def _duplicate(self, entries: List[Entry], kind: Kind, model: Any, skip: Optional[Entry]) -> Optional[Dict[str, str]]:
        identity = _key_and_label(kind, model)
        if identity is None:
            return None
        field_name = kind.identity[0]
        for entry in entries:
            if entry is skip or not entry.kind.is_list:
                continue
            if entry.key.lower() == identity[0].lower():
                return {field_name: "already configured"}
            if kind.id == "rss" and entry.kind.id == "rss" and (
                str(entry.model.url).rstrip("/").lower() == str(model.url).rstrip("/").lower()
            ):
                return {"url": "this feed is already configured"}
        return None

    def add(self, body: Dict[str, Any]) -> Response:
        kind = KINDS.get(body.get("kind"))  # type: ignore[arg-type]
        if kind is None or not kind.is_list:
            return HTTPStatus.BAD_REQUEST, {"error": "unknown source kind"}
        cleaned, errors = clean_values(kind, body.get("values"), adding=True)
        errors = errors or self._check_url(cleaned) or {}
        if errors:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid source", "fields": errors}
        new_raw = {**kind.match, **_raw_fields(kind, cleaned)}
        new_raw.setdefault("enabled", True)

        def mutate(raw: Dict[str, Any]) -> Optional[Response]:
            config = self.settings._validate(raw)
            entries = list_entries(raw, config)
            try:
                model = _model_class(kind)(**new_raw)
            except ValidationError as exc:
                return _validation_fields(kind, exc)
            duplicate = self._duplicate(entries, kind, model, None)
            if duplicate:
                return HTTPStatus.CONFLICT, {"error": "duplicate source", "fields": duplicate}
            sources = raw.setdefault("sources", {})
            if kind.path in (("rss",), ("github",)) and config.sector != DEFAULT_SECTOR:
                new_raw["sector"] = config.sector  # a source added in a sector leaves and returns with it
            _container(sources, kind.path, create=True).append(new_raw)
            return None

        refusal = self.settings.edit_raw(body.get("version"), mutate, lambda exc: _validation_fields(kind, exc))
        return refusal or self._created(kind, new_raw)

    def _created(self, kind: Kind, new_raw: Dict[str, Any]) -> Response:
        status, payload = self.list()
        model = _model_class(kind)(**new_raw)
        identity = _key_and_label(kind, model)
        payload["key"] = identity[0] if identity else None
        return HTTPStatus.CREATED, payload

    def update(self, key: str, body: Dict[str, Any]) -> Response:
        holder: Dict[str, Any] = {}

        def mutate(raw: Dict[str, Any]) -> Optional[Response]:
            config = self.settings._validate(raw)
            entries = list_entries(raw, config)
            entry = next((entry for entry in entries if entry.key == key), None)
            if entry is None:
                return HTTPStatus.NOT_FOUND, {"error": "source not found"}
            kind = entry.kind
            if kind.readonly:
                return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "this source is read only here"}
            cleaned, errors = clean_values(kind, body.get("values"), adding=False)
            current = _values(entry)
            changed = {
                name: value
                for name, value in cleaned.items()
                if name == "enabled" and value != _enabled(entry) or name != "enabled" and value != current.get(name)
            }
            if _locked(entry):
                for name in changed:
                    if name != "enabled":
                        errors[name] = "set through an environment variable in config.json"
            errors = errors or self._check_url(changed) or {}
            if errors:
                return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid source", "fields": errors}
            if not changed:
                holder["key"] = key
                return None
            target = entry.raw
            if target is None:  # a section absent from the file (GDELT, Google News)
                target = raw.setdefault("sources", {}).setdefault(kind.path[0], {})
                if not isinstance(target, dict):
                    target = raw["sources"][kind.path[0]] = {}
            target.update(_raw_fields(kind, changed))
            if kind.is_list:
                try:
                    model = _model_class(kind)(**target)
                except ValidationError as exc:
                    return _validation_fields(kind, exc)
                duplicate = self._duplicate(entries, kind, model, entry)
                if duplicate:
                    return HTTPStatus.CONFLICT, {"error": "duplicate source", "fields": duplicate}
                identity = _key_and_label(kind, model)
                holder["key"] = identity[0] if identity else key
            else:
                holder["key"] = key
            holder["kind"] = kind
            return None

        refusal = self.settings.edit_raw(
            body.get("version"), mutate, lambda exc: _validation_fields(holder.get("kind") or KINDS["rss"], exc)
        )
        if refusal:
            return refusal
        status, payload = self.list()
        payload["key"] = holder.get("key", key)
        return status, payload

    def delete(self, key: str, body: Dict[str, Any]) -> Response:
        def mutate(raw: Dict[str, Any]) -> Optional[Response]:
            config = self.settings._validate(raw)
            entry = next((entry for entry in list_entries(raw, config) if entry.key == key), None)
            if entry is None:
                return HTTPStatus.NOT_FOUND, {"error": "source not found"}
            if not entry.kind.is_list:
                return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "this source can only be disabled"}
            container = _container(raw["sources"], entry.kind.path)
            del container[entry.index]
            return None

        refusal = self.settings.edit_raw(body.get("version"), mutate, lambda exc: _validation_fields(KINDS["rss"], exc))
        return refusal or self.list()

    # Test --------------------------------------------------------------------------

    def test(self, body: Dict[str, Any]) -> Response:
        """Fetch one source now, without AI or archive: {key} for a saved one, or {kind, values}."""
        raw, _, config = self.settings.snapshot()
        if isinstance(body.get("key"), str):
            entry = next((entry for entry in list_entries(raw, config) if entry.key == body["key"]), None)
            if entry is None:
                return HTTPStatus.NOT_FOUND, {"error": "source not found"}
            kind = entry.kind
            if kind.readonly or kind.is_group:
                return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "this source cannot be tested here"}
            model = entry.model if entry.model is not None else _default_model(kind)
            model = model.model_copy(update={"enabled": True})
            url = str(model.url) if kind.id == "rss" else None
        else:
            kind = KINDS.get(body.get("kind"))  # type: ignore[arg-type]
            if kind is None or kind.readonly or kind.is_group:
                return HTTPStatus.BAD_REQUEST, {"error": "unknown or untestable source kind"}
            cleaned, errors = clean_values(kind, body.get("values"), adding=kind.is_list)
            errors = errors or self._check_url(cleaned) or {}
            if errors:
                return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid source", "fields": errors}
            fields = {**kind.match, **_raw_fields(kind, cleaned), "enabled": True}
            try:
                model = _model_class(kind)(**fields)
            except ValidationError as exc:
                return _validation_fields(kind, exc)
            url = cleaned.get("url")
        if url is not None:
            try:
                asyncio.run(self.resolve_public(url))
            except UnsafeURLError as exc:
                return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid source", "fields": {"url": str(exc)}}
        result = asyncio.run(self._run_test(kind, model, config.collection.time_window_hours))
        result["window_hours"] = config.collection.time_window_hours
        return HTTPStatus.OK, _scrub(result, raw)

    async def _run_test(self, kind: Kind, model: Any, window_hours: int) -> Dict[str, Any]:
        started = time.monotonic()
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=window_hours)
        warnings = _WarningCollector()

        async def check_request(request: httpx.Request) -> None:
            await self.resolve_public(str(request.url))  # redirects too

        items: List[Any] = []
        error: Optional[str] = None
        logger = logging.getLogger("lucidnews.scrapers")
        logger.addHandler(warnings)
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"User-Agent": COLLECTOR_USER_AGENT},
                event_hooks={"request": [check_request]},
            ) as client:
                scraper = _scraper(kind, model, client)
                items = await asyncio.wait_for(
                    scraper.fetch(now - timedelta(days=TEST_LOOKBACK_DAYS)), TEST_TIMEOUT_SECONDS
                )
                source_errors = list(getattr(scraper, "source_errors", {}).values())
                if source_errors:
                    error = source_errors[0]
        except asyncio.TimeoutError:
            error = f"no answer after {TEST_TIMEOUT_SECONDS} s"
        except Exception as exc:  # the test reports any failure instead of raising
            error = short_error(exc)
        finally:
            logger.removeHandler(warnings)
        if error is None and not items and warnings.messages:
            error = warnings.messages[0]
        items = sorted(items, key=lambda item: item.published_at, reverse=True)
        return {
            "ok": error is None,
            "count": len(items),
            "in_window": sum(1 for item in items if item.published_at >= window_start),
            "days": TEST_LOOKBACK_DAYS,
            "error": error,
            "warnings": warnings.messages[:3] if error is None else [],
            "duration_ms": int((time.monotonic() - started) * 1000),
            "sample": [
                {"title": html.unescape(item.title), "url": str(item.url), "published_at": item.published_at.isoformat()}
                for item in items[:TEST_SAMPLE_SIZE]
            ],
        }


class _WarningCollector(logging.Handler):
    """Scrapers log and skip what fails: the test turns those warnings into its answer."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage().splitlines()[0][:300]
        except Exception:  # a bad log call must not break the test
            return
        if message not in self.messages:
            self.messages.append(message)


def _model_class(kind: Kind) -> Any:
    return {
        "rss": RSSSourceConfig,
        "github_repo": GitHubSourceConfig,
        "github_user": GitHubSourceConfig,
        "reddit_subreddit": RedditSubredditConfig,
        "reddit_user": RedditUserConfig,
        "telegram_channel": TelegramChannelConfig,
        "hackernews": HackerNewsConfig,
        "ossinsight": OSSInsightConfig,
        "gdelt": GDELTConfig,
        "google_news": GoogleNewsConfig,
    }[kind.id]


def _scraper(kind: Kind, model: Any, client: httpx.AsyncClient) -> Any:
    from .scrapers.gdelt import GDELTScraper
    from .scrapers.github import GitHubScraper
    from .scrapers.google_news import GoogleNewsScraper
    from .scrapers.hackernews import HackerNewsScraper
    from .scrapers.ossinsight import OSSInsightScraper
    from .scrapers.reddit import RedditScraper
    from .scrapers.rss import RSSScraper
    from .scrapers.telegram import TelegramScraper

    if kind.id == "rss":
        return RSSScraper([model], client)
    if kind.id in ("github_repo", "github_user"):
        return GitHubScraper([model], client)
    if kind.id == "reddit_subreddit":
        return RedditScraper(RedditConfig(subreddits=[model], fetch_comments=0), client)
    if kind.id == "reddit_user":
        return RedditScraper(RedditConfig(users=[model], fetch_comments=0), client)
    if kind.id == "telegram_channel":
        return TelegramScraper(TelegramConfig(channels=[model]), client)
    if kind.id == "hackernews":
        return HackerNewsScraper(model, client)
    if kind.id == "ossinsight":
        return OSSInsightScraper(model, client)
    if kind.id == "gdelt":
        return GDELTScraper(model, client)
    return GoogleNewsScraper(model, client)


def _scrub(result: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    """Hide values of ${VARIABLES} (a token in a feed URL) from what the test returns."""
    secrets = {
        match.group(1): os.environ[match.group(1)]
        for match in _ENV_VAR_PATTERN.finditer(json.dumps(raw))
        if len(os.environ.get(match.group(1), "")) >= 4
    }
    if not secrets:
        return result
    text = json.dumps(result)
    for name, value in secrets.items():
        text = text.replace(json.dumps(value)[1:-1], f"${{{name}}}")
    return json.loads(text)
