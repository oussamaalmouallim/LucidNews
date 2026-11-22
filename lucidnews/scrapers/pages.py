"""Official list pages without a feed, read as feeds (chantier « Nouveaux secteurs », lot 1.6).

Many authorities publish their communiqués, decisions or deliberations on a list page and no
RSS. This reader turns such a page into news, politely:

- the site's ``robots.txt`` is read first; a page it disallows is never fetched;
- one request per page and per run, one site after the other, with a pause between sites;
- a block without a date is not a news and is skipped: a page read at every run must not bring
  the same communiqué back as new.

Items look like RSS items (``feed_name``, key ``rss/<name>``): health, quality, the archive and
the edition treat a page like any feed.
"""

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from ..models import ContentItem, PageSourceConfig, SourceType
from ..source_health import rss_key
from .base import BaseScraper, short_error

logger = logging.getLogger(__name__)

USER_AGENT = "LucidNews (+https://github.com/StackLLM/LucidNews)"
PAUSE_BETWEEN_SITES = 2.0
FRENCH_MONTHS = {
    "janvier": "January", "février": "February", "fevrier": "February", "mars": "March", "avril": "April",
    "mai": "May", "juin": "June", "juillet": "July", "août": "August", "aout": "August",
    "septembre": "September", "octobre": "October", "novembre": "November", "décembre": "December", "decembre": "December",
}
_FRENCH = re.compile("|".join(sorted(FRENCH_MONTHS, key=len, reverse=True)), re.IGNORECASE)


@dataclass(frozen=True)
class PageEntry:
    title: str
    url: str
    published_at: datetime


# The first date of a text: 22/11/2026, 22.11.2026, 22 November 2026 (after French months are translated).
_FIRST_DATE = re.compile(
    r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{4}\b|\b\d{1,2}(?:er)? [A-Za-z]+\.? \d{4}\b", re.IGNORECASE
)


def parse_date(text: str) -> Optional[datetime]:
    """A date written on a page, French or English, day first (22/11/2026, 22 novembre 2026).

    An ISO date (2026-11-05, a ``datetime`` attribute) is year, month, day: never read day first.
    A text with two dates ("published 14/11/2025 - updated 19/11/2026") gives the first one."""
    raw = text.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        try:
            moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            moment = None
        if moment is not None:
            return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    cleaned = _FRENCH.sub(lambda match: FRENCH_MONTHS[match.group(0).lower()], raw)
    cleaned = re.sub(r"\b(le|du|publié|published|on)\b", " ", cleaned, flags=re.IGNORECASE)
    try:
        moment = date_parser.parse(cleaned, dayfirst=True, fuzzy=True)
    except (ValueError, OverflowError):
        first = _FIRST_DATE.search(cleaned)
        if first is None:
            return None
        try:
            moment = date_parser.parse(first.group(0).replace("er ", " "), dayfirst=True)
        except (ValueError, OverflowError):
            return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def parse_list_page(html: str, page: PageSourceConfig) -> List[PageEntry]:
    """The dated news of a list page, in page order, links made absolute, same site only."""
    soup = BeautifulSoup(html, "html.parser")
    host = urlsplit(str(page.url)).hostname
    # Relative links resolve against the page's <base href> when it declares one (CJEU does).
    declared = soup.find("base", href=True)
    base = urljoin(str(page.url), str(declared["href"])) if declared is not None else str(page.url)
    entries: List[PageEntry] = []
    seen = set()
    for block in soup.select(page.item_selector):
        link = block.select_one(page.link_selector) if page.link_selector else None
        date = block.select_one(page.date_selector) if page.date_selector else None
        if link is None or not link.get("href") or date is None:
            continue
        url = urljoin(base, str(link["href"]))
        holder = block.select_one(page.title_selector) if page.title_selector else link
        title = " ".join(holder.get_text(" ").split()) if holder is not None else ""
        if not title or urlsplit(url).scheme != "https" or urlsplit(url).hostname != host or url in seen:
            continue
        published = parse_date(str(date.get("datetime") or date.get_text(" ")))
        if published is None:
            continue
        seen.add(url)
        entries.append(PageEntry(title, url, published))
        if len(entries) == page.max_items:
            break
    return entries


async def robots_allow(client: httpx.AsyncClient, url: str) -> bool:
    """What the site's robots.txt says of ``url`` for us. No robots.txt (404): allowed."""
    parts = urlsplit(url)
    response = await client.get(f"{parts.scheme}://{parts.netloc}/robots.txt", headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    if response.status_code in (401, 403):
        return False
    if response.status_code != 200:
        return True
    rules = RobotFileParser()
    rules.parse(response.text.splitlines())
    return rules.can_fetch(USER_AGENT, url)


class PageListScraper(BaseScraper):
    def __init__(self, pages: List[PageSourceConfig], http_client: httpx.AsyncClient, pause: float = PAUSE_BETWEEN_SITES):
        super().__init__({"pages": pages}, http_client)
        self.pause = pause

    async def fetch(self, since: datetime) -> List[ContentItem]:
        items: List[ContentItem] = []
        first = True
        for page in self.config["pages"]:
            if not page.enabled:
                continue
            if not first:
                await asyncio.sleep(self.pause)
            first = False
            items.extend(await self._fetch_page(page, since))
        return items

    async def _fetch_page(self, page: PageSourceConfig, since: datetime) -> List[ContentItem]:
        key = rss_key(page.name)
        try:
            if not await robots_allow(self.client, str(page.url)):
                self.source_errors[key] = "robots.txt disallows this page"
                return []
            # Like the feeds and the checker, follow a redirect (CJEU, EDPB): the page moved, it is still theirs.
            response = await self.client.get(str(page.url), headers={"User-Agent": USER_AGENT}, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self.source_errors[key] = short_error(exc)
            return []
        items = []
        for entry in parse_list_page(response.text, page):
            if entry.published_at < since:
                continue
            native = hashlib.sha256(entry.url.encode()).hexdigest()[:16]
            items.append(
                ContentItem(
                    id=self._generate_id("rss", hashlib.sha256(page.name.encode()).hexdigest()[:8], native),
                    source_type=SourceType.RSS,
                    title=entry.title,
                    url=entry.url,
                    author=page.name,
                    published_at=entry.published_at,
                    profile=page.profile,
                    metadata={
                        "feed_name": page.name,
                        "category": page.category,
                        "page_source": True,
                        **({"source_trust": page.trust.value} if page.trust else {}),
                    },
                )
            )
        return items
