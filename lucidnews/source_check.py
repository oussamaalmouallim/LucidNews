"""Check the sources of a sector catalog before they ship (chantier « Nouveaux secteurs », lot 1.5).

Every source is read for real, the way a run would read it, and kept only if:

- its address is HTTPS;
- it answers 200 with a feed that parses;
- it has news with a title and a link;
- its newest news is less than ``max_age_days`` old (a dead feed is worse than none).

The result is a dated Markdown report, source by source: kept or set aside, and why. It needs the
network, so the CI does not run it; ``tests/test_source_check.py`` checks the rules on fixed feeds.

    uv run lucidnews-sources-check tech --out docs/sources/verification/tech-2026-11-22.md
"""

import argparse
import asyncio
import calendar
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Tuple

import feedparser
import httpx

from .models import PageSourceConfig
from .sector_catalog import CatalogError, load_sector_catalog

USER_AGENT = "LucidNews source check (+https://github.com/StackLLM/LucidNews)"
MAX_AGE_DAYS = 30
TIMEOUT_SECONDS = 20
PARALLEL = 6

Fetch = Callable[[str], Awaitable[Tuple[int, bytes]]]


@dataclass
class Verdict:
    name: str
    url: str
    reasons: List[str] = field(default_factory=list)
    entries: int = 0
    newest: Optional[datetime] = None

    @property
    def kept(self) -> bool:
        return not self.reasons


FUTURE_SLACK = timedelta(days=1)  # time zones and clocks; beyond it, a date is in the future


def _entry_time(entry: dict) -> Optional[datetime]:
    for key in ("published", "updated"):
        value = entry.get(f"{key}_parsed")
        if value:
            return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc)
        # The collector reads a date feedparser could not ("Sun,22 Nov 2026", the Senate's): so do we.
        if entry.get(key):
            try:
                moment = parsedate_to_datetime(str(entry[key]))
            except (TypeError, ValueError):
                continue
            return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return None


def judge_feed(name: str, url: str, status: int, body: bytes, now: datetime, max_age_days: int = MAX_AGE_DAYS) -> Verdict:
    """The rules, without the network: what was fetched decides."""
    verdict = Verdict(name, url)
    if not url.lower().startswith("https://"):
        verdict.reasons.append("not HTTPS")
    if status != 200:
        verdict.reasons.append(f"HTTP {status}")
        return verdict
    parsed = feedparser.parse(body)
    usable = [entry for entry in parsed.entries if entry.get("title") and entry.get("link")]
    verdict.entries = len(usable)
    if not usable:
        # feedparser names the format it recognised (rss20, atom10…); nothing means it is no feed at all.
        verdict.reasons.append("no news with a title and a link" if parsed.get("version") else "not a feed")
        return verdict
    # A date in the future (an event announced ahead, a wrong clock) says nothing of freshness.
    dates = [moment for moment in (_entry_time(entry) for entry in usable) if moment is not None and moment <= now + FUTURE_SLACK]
    verdict.newest = max(dates) if dates else None
    if verdict.newest is None:
        verdict.reasons.append("no dated news")
    elif now - verdict.newest > timedelta(days=max_age_days):
        verdict.reasons.append(f"newest news is {(now - verdict.newest).days} days old")
    return verdict


async def check_feeds(
    feeds: List[Tuple[str, str]], fetch: Fetch, now: Optional[datetime] = None, max_age_days: int = MAX_AGE_DAYS
) -> List[Verdict]:
    now = now or datetime.now(timezone.utc)
    gate = asyncio.Semaphore(PARALLEL)

    async def one(name: str, url: str) -> Verdict:
        async with gate:
            try:
                status, body = await fetch(url)
            except (httpx.HTTPError, OSError) as exc:
                return Verdict(name, url, [f"unreachable ({type(exc).__name__})"])
        return judge_feed(name, url, status, body, now, max_age_days)

    return list(await asyncio.gather(*(one(name, url) for name, url in feeds)))


def judge_page(page: PageSourceConfig, allowed: bool, status: int, html: str, now: datetime, max_age_days: int = MAX_AGE_DAYS) -> Verdict:
    """A list page is kept on the same terms as a feed, and only if robots.txt lets us read it."""
    from .scrapers.pages import parse_list_page

    verdict = Verdict(page.name, str(page.url))
    if not allowed:
        verdict.reasons.append("robots.txt disallows this page")
        return verdict
    if status != 200:
        verdict.reasons.append(f"HTTP {status}")
        return verdict
    entries = parse_list_page(html, page)
    verdict.entries = len(entries)
    if not entries:
        verdict.reasons.append("no dated news found with the selectors")
        return verdict
    dates = [entry.published_at for entry in entries if entry.published_at <= now + FUTURE_SLACK]
    verdict.newest = max(dates) if dates else None
    if verdict.newest is None:
        verdict.reasons.append("no dated news")
    elif now - verdict.newest > timedelta(days=max_age_days):
        verdict.reasons.append(f"newest news is {(now - verdict.newest).days} days old")
    return verdict


def render_report(sector: str, verdicts: List[Verdict], now: datetime, queries: List[str]) -> str:
    kept = [verdict for verdict in verdicts if verdict.kept]
    lines = [
        f"# Vérification des sources — secteur `{sector}`",
        "",
        f"Le {now:%Y-%m-%d à %H:%M} UTC. **{len(kept)} gardées sur {len(verdicts)}.**",
        "",
        "| Source | Verdict | News lues | Plus récente | Raison |",
        "|---|---|---|---|---|",
    ]
    for verdict in sorted(verdicts, key=lambda entry: (entry.kept, entry.name.lower())):
        newest = f"{verdict.newest:%Y-%m-%d}" if verdict.newest else "—"
        state = "gardée" if verdict.kept else "**écartée**"
        lines.append(f"| [{verdict.name}]({verdict.url}) | {state} | {verdict.entries} | {newest} | {'; '.join(verdict.reasons) or '—'} |")
    if queries:
        lines += ["", "Recherches par mot-clé (non lues ici, elles dépendent de la requête) :", ""]
        lines += [f"- {query}" for query in queries]
    return "\n".join(lines) + "\n"


async def _http_fetch_factory() -> Tuple[httpx.AsyncClient, Fetch]:
    client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True, headers={"User-Agent": USER_AGENT})

    async def fetch(url: str) -> Tuple[int, bytes]:
        response = await client.get(url)
        return response.status_code, response.content

    return client, fetch


async def _run(sector: str, max_age_days: int) -> Tuple[List[Verdict], List[str]]:
    catalog = load_sector_catalog(sector)
    feeds = [(feed.name, str(feed.url)) for feed in catalog.sources.rss if "${" not in str(feed.url)]
    queries = [f"{name} : {block.query}" for name, block in (("GDELT", catalog.sources.gdelt), ("Google News", catalog.sources.google_news)) if block is not None and block.enabled]
    client, fetch = await _http_fetch_factory()
    async with client:
        verdicts = await check_feeds(feeds, fetch, max_age_days=max_age_days)
        verdicts += await check_pages(catalog.sources.pages, client, max_age_days)
        return verdicts, queries


async def check_pages(pages: List[PageSourceConfig], client: httpx.AsyncClient, max_age_days: int = MAX_AGE_DAYS) -> List[Verdict]:
    from .scrapers.pages import robots_allow

    now = datetime.now(timezone.utc)
    verdicts = []
    for page in pages:
        try:
            allowed = await robots_allow(client, str(page.url))
            response = await client.get(str(page.url)) if allowed else None
        except httpx.HTTPError as exc:
            verdicts.append(Verdict(page.name, str(page.url), [f"unreachable ({type(exc).__name__})"]))
            continue
        status, html = (response.status_code, response.text) if response is not None else (0, "")
        verdicts.append(judge_page(page, allowed, status, html, now, max_age_days))
    return verdicts


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Read every source of a sector catalog and say which ones to keep")
    parser.add_argument("sector")
    parser.add_argument("--out", type=Path, help="write the Markdown report here (default: print it)")
    parser.add_argument("--max-age-days", type=int, default=MAX_AGE_DAYS)
    args = parser.parse_args(argv)
    try:
        verdicts, queries = asyncio.run(_run(args.sector, args.max_age_days))
    except CatalogError as exc:
        print(f"Cannot read the catalog: {exc}", file=sys.stderr)
        return 2
    report = render_report(args.sector, verdicts, datetime.now(timezone.utc), queries)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"Report written to {args.out}", file=sys.stderr)
    else:
        print(report)
    rejected = sum(1 for verdict in verdicts if not verdict.kept)
    print(f"{len(verdicts) - rejected} kept, {rejected} set aside.", file=sys.stderr)
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
