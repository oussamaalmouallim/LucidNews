"""Chantier « Nouveaux secteurs », lot 1.6 — an official list page without a feed becomes a source
like any other: dated news only, same site only, robots.txt obeyed. No network: a mock transport."""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from lucidnews.models import Config, PageSourceConfig
from lucidnews.scrapers.pages import PageListScraper, parse_date, parse_list_page
from lucidnews.source_check import judge_page
from lucidnews.source_health import configured_source_keys
from tests.test_auth import ROOT

NOW = datetime.now(timezone.utc)
RECENT = (NOW - timedelta(days=3)).strftime("%d/%m/%Y")
OLD = "12 janvier 2020"
PAGE = PageSourceConfig(
    name="Autorité — communiqués",
    url="https://autorite.example/communiques",
    item_selector="li.communique",
    date_selector="span.date",
    category="fake-markets",
)
HTML = f"""<html><body><ul>
  <li class="communique"><a href="/communiques/sanction-x">Sanction contre la société X</a> <span class="date">{RECENT}</span></li>
  <li class="communique"><a href="https://autorite.example/communiques/ancien">Ancien communiqué</a> <span class="date">{OLD}</span></li>
  <li class="communique"><a href="/communiques/sans-date">Sans date</a></li>
  <li class="communique"><a href="https://ailleurs.example/pub">Lien vers un autre site</a> <span class="date">{RECENT}</span></li>
  <li class="communique"><a href="/communiques/sanction-x">Sanction contre la société X</a> <span class="date">{RECENT}</span></li>
</ul></body></html>"""


def client(robots: str = "", status: int = 200) -> httpx.AsyncClient:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200 if robots else 404, text=robots)
        return httpx.Response(status, text=HTML)

    return httpx.AsyncClient(transport=httpx.MockTransport(answer))


def test_dates_are_read_in_french_and_english_day_first() -> None:
    assert parse_date("22/11/2026").date().isoformat() == "2026-11-22"
    assert parse_date("Publié le 3 décembre 2026").date().isoformat() == "2026-12-03"
    assert parse_date("November 5, 2026").date().isoformat() == "2026-11-05"
    assert parse_date("bientôt") is None


def test_only_dated_news_of_the_same_site_are_kept_once() -> None:
    entries = parse_list_page(HTML, PAGE)
    assert [entry.title for entry in entries] == ["Sanction contre la société X", "Ancien communiqué"]
    assert entries[0].url == "https://autorite.example/communiques/sanction-x"


def test_the_page_becomes_news_like_a_feed() -> None:
    async def run():  # type: ignore[no-untyped-def]
        async with client() as http:
            scraper = PageListScraper([PAGE], http, pause=0)
            return await scraper.fetch(NOW - timedelta(days=30)), scraper.source_errors

    items, errors = asyncio.run(run())
    assert errors == {}
    assert [item.title for item in items] == ["Sanction contre la société X"]  # the 2020 one is before ``since``
    assert items[0].metadata["feed_name"] == "Autorité — communiqués" and items[0].metadata["category"] == "fake-markets"


def test_a_page_robots_txt_disallows_is_never_fetched() -> None:
    fetched = []

    def answer(request: httpx.Request) -> httpx.Response:
        fetched.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /communiques")
        return httpx.Response(200, text=HTML)

    async def run():  # type: ignore[no-untyped-def]
        async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as http:
            scraper = PageListScraper([PAGE], http, pause=0)
            return await scraper.fetch(NOW - timedelta(days=30)), scraper.source_errors

    items, errors = asyncio.run(run())
    assert items == [] and fetched == ["/robots.txt"]
    assert errors == {"rss/Autorité — communiqués": "robots.txt disallows this page"}


def test_a_page_source_must_be_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        PageSourceConfig(name="X", url="http://autorite.example/", item_selector="li")


def test_the_checker_judges_a_page_like_a_feed() -> None:
    assert judge_page(PAGE, True, 200, HTML, NOW).kept
    assert judge_page(PAGE, False, 0, "", NOW).reasons == ["robots.txt disallows this page"]
    assert judge_page(PAGE, True, 200, "<html></html>", NOW).reasons == ["no dated news found with the selectors"]
    stale = HTML.replace(RECENT, "01/01/2025")
    assert judge_page(PAGE, True, 200, stale, NOW).reasons[0].startswith("newest news is")


def test_a_page_is_a_configured_source_with_a_feed_key() -> None:
    raw = json.loads((ROOT / "data" / "config.example.json").read_text())
    raw["sources"]["pages"] = [{**PAGE.model_dump(mode="json", exclude_none=True), "category": None}]
    keys = configured_source_keys(Config.model_validate(raw))
    assert keys["rss/Autorité — communiqués"] == "rss"
