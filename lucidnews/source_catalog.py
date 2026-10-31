"""Catalog of recommended sources, by taxonomy category (lot 18).

Built from what the project already ships, nothing invented:

- the curated feeds and repositories of ``data/config.example.json``, whose
  ``category`` is one of the 12 categories;
- the setup wizard catalog ``data/presets.json``, whose domains are mapped to
  categories (its science domain is outside IT and left out).

A recommendation is a catalog source that is **not** in the configuration, in any
state. Entries carry the ``kind`` and ``values`` the sources API adds, and the key
the health report uses.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .models import Config
from .source_health import github_repo_key, github_user_key, rss_key
from .sectors import all_categories
from .taxonomy import Category

PROJECT_DATA = Path(__file__).resolve().parents[1] / "data"
PRESET_CATEGORIES = {
    "ai-ml": Category.AI.value,
    "systems": Category.INFRASTRUCTURE.value,
    "security": Category.CYBERSECURITY.value,
    "webdev": Category.WEB.value,
    "pl": Category.SOFTWARE_DEVELOPMENT.value,
    "embedded": Category.EMERGING_TECH.value,
    "devtools": Category.DEVELOPER_TOOLS.value,
}
# Feeds that need a key (${VAR}) or a removed integration are not recommended.
EXCLUDED_URL_PARTS = ("${", "wechat2rss")


@dataclass(frozen=True)
class CatalogEntry:
    key: str
    kind: str
    label: str
    category: str
    values: Dict[str, object]
    description: Optional[str]
    origin: str  # example | presets

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _entry(kind: str, values: Dict[str, object], category: str, description: Optional[str], origin: str) -> Optional[CatalogEntry]:
    if kind == "rss":
        url = str(values.get("url") or "")
        if not values.get("name") or not url or any(part in url for part in EXCLUDED_URL_PARTS):
            return None
        return CatalogEntry(rss_key(str(values["name"])), kind, str(values["name"]), category,
                            {"name": values["name"], "url": url}, description, origin)
    if kind == "github_repo" and values.get("owner") and values.get("repo"):
        repository = f"{values['owner']}/{values['repo']}"
        return CatalogEntry(github_repo_key(str(values["owner"]), str(values["repo"])), kind, repository,
                            category, {"repository": repository}, description, origin)
    if kind == "github_user" and values.get("username"):
        return CatalogEntry(github_user_key(str(values["username"])), kind, f"@{values['username']}", category,
                            {"username": values["username"]}, description, origin)
    if kind == "reddit_subreddit" and values.get("subreddit"):
        fields = {name: values[name] for name in ("subreddit", "sort", "fetch_limit", "min_score") if name in values}
        return CatalogEntry(f"reddit/r/{values['subreddit']}", kind, f"r/{values['subreddit']}", category,
                            fields, description, origin)
    return None


def load_catalog(data_dir: Path = PROJECT_DATA) -> List[CatalogEntry]:
    known = {category.id for category in all_categories()}
    entries: List[CatalogEntry] = []

    example_path = data_dir / "config.example.json"
    if example_path.exists():
        sources = json.loads(example_path.read_text(encoding="utf-8")).get("sources", {})
        for feed in sources.get("rss", []):
            if feed.get("category") in known:
                entries.append(_entry("rss", feed, feed["category"], None, "example"))  # type: ignore[arg-type]
        for repo in sources.get("github", []):
            if repo.get("category") in known and repo.get("type") == "repo_releases":
                entries.append(_entry("github_repo", repo, repo["category"], None, "example"))  # type: ignore[arg-type]

    presets_path = data_dir / "presets.json"
    if presets_path.exists():
        for domain in json.loads(presets_path.read_text(encoding="utf-8")).get("domains", []):
            category = PRESET_CATEGORIES.get(domain.get("id"))
            if category is None:
                continue
            for source in domain.get("sources", []):
                entries.append(
                    _entry(source.get("type", ""), source.get("config", {}), category, source.get("description"), "presets")  # type: ignore[arg-type]
                )

    unique: Dict[str, CatalogEntry] = {}
    for entry in entries:
        if entry is not None and entry.key.lower() not in unique:
            unique[entry.key.lower()] = entry
    return list(unique.values())


def configured_identities(config: Config) -> Tuple[Set[str], Set[str]]:
    """Every configured source, enabled or not: (lower-case keys, normalized feed URLs)."""
    sources = config.sources
    keys: Set[str] = set()
    urls: Set[str] = set()
    for feed in sources.rss:
        keys.add(rss_key(feed.name).lower())
        urls.add(_normalized_url(str(feed.url)))
    for entry in sources.github:
        if entry.owner and entry.repo:
            keys.add(github_repo_key(entry.owner, entry.repo).lower())
        if entry.username:
            keys.add(github_user_key(entry.username).lower())
    for subreddit in sources.reddit.subreddits:
        keys.add(f"reddit/r/{subreddit.subreddit}".lower())
    for user in sources.reddit.users:
        keys.add(f"reddit/u/{user.username}".lower())
    for channel in sources.telegram.channels:
        keys.add(f"telegram/@{channel.channel}".lower())
    return keys, urls


def _normalized_url(url: str) -> str:
    return url.rstrip("/").lower()


def recommendations(
    catalog: List[CatalogEntry], config: Config, category: Optional[str] = None
) -> List[CatalogEntry]:
    """Catalog sources absent from the configuration (by key or by feed URL)."""
    keys, urls = configured_identities(config)
    return [
        entry
        for entry in catalog
        if (category is None or entry.category == category)
        and entry.key.lower() not in keys
        and not (entry.kind == "rss" and _normalized_url(str(entry.values["url"])) in urls)
    ]
