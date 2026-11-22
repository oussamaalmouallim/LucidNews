"""Chantier « Nouveaux secteurs », lot 1.5 — the source checker keeps a feed only if it is HTTPS,
answers, parses, has news with a title and a link, and is alive. No network: fixed feeds."""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from lucidnews.source_check import check_feeds, judge_feed, render_report

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)


def rss(*items: tuple[str, str, datetime]) -> bytes:
    entries = "".join(
        f"<item><title>{title}</title><link>{link}</link><pubDate>{when:%a, %d %b %Y %H:%M:%S +0000}</pubDate></item>"
        for title, link, when in items
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>{entries}</channel></rss>'.encode()


FRESH = rss(("Taux directeurs", "https://example.org/1", NOW - timedelta(days=2)), ("Bourse", "https://example.org/2", NOW - timedelta(days=5)))


def test_a_live_https_feed_is_kept() -> None:
    verdict = judge_feed("Banque", "https://example.org/feed", 200, FRESH, NOW)
    assert verdict.kept and verdict.entries == 2 and verdict.newest == NOW - timedelta(days=2)


def test_each_fault_is_named() -> None:
    assert judge_feed("A", "http://example.org/feed", 200, FRESH, NOW).reasons == ["not HTTPS"]
    assert judge_feed("B", "https://example.org/feed", 404, b"", NOW).reasons == ["HTTP 404"]
    assert judge_feed("C", "https://example.org/feed", 200, b"<html><body>Bienvenue</body></html>", NOW).reasons == ["not a feed"]
    old = rss(("Ancien", "https://example.org/old", NOW - timedelta(days=90)))
    assert judge_feed("D", "https://example.org/feed", 200, old, NOW).reasons == ["newest news is 90 days old"]
    untitled = b'<?xml version="1.0"?><rss version="2.0"><channel><title>T</title><item><link>https://x.org</link></item></channel></rss>'
    assert judge_feed("E", "https://example.org/feed", 200, untitled, NOW).reasons == ["no news with a title and a link"]


def test_an_unreachable_source_is_set_aside_and_the_others_still_checked() -> None:
    async def fetch(url: str) -> tuple[int, bytes]:
        if "down" in url:
            raise httpx.ConnectError("refused")
        return 200, FRESH

    verdicts = asyncio.run(check_feeds([("Up", "https://up.example/f"), ("Down", "https://down.example/f")], fetch, NOW))
    assert [(verdict.name, verdict.kept) for verdict in verdicts] == [("Up", True), ("Down", False)]
    assert verdicts[1].reasons == ["unreachable (ConnectError)"]


def test_the_report_says_what_is_kept_and_why_the_rest_is_not() -> None:
    verdicts = [judge_feed("Banque", "https://example.org/feed", 200, FRESH, NOW), judge_feed("Mort", "https://example.org/dead", 410, b"", NOW)]
    report = render_report("finance", verdicts, NOW, ["GDELT : banque OR bourse"])
    assert "**1 gardées sur 2.**" in report
    assert "| [Mort](https://example.org/dead) | **écartée** | 0 | — | HTTP 410 |" in report
    assert report.index("Mort") < report.index("Banque")  # what needs attention comes first
    assert "GDELT : banque OR bourse" in report


def test_a_date_in_the_future_does_not_make_a_stale_feed_look_fresh() -> None:
    # Phase 2: a feed announced an event months ahead; its real news were old.
    body = rss(("Conférence 2027", "https://example.org/event", NOW + timedelta(days=90)), ("Vieux", "https://example.org/old", NOW - timedelta(days=60)))
    verdict = judge_feed("Agenda", "https://example.org/feed", 200, body, NOW)
    assert not verdict.kept and verdict.newest == NOW - timedelta(days=60)
    only_future = rss(("Conférence 2027", "https://example.org/event", NOW + timedelta(days=90)))
    assert judge_feed("Agenda", "https://example.org/feed", 200, only_future, NOW).reasons == ["no dated news"]
    # A few hours ahead is a time zone, not the future.
    soon = rss(("Ce matin", "https://example.org/now", NOW + timedelta(hours=5)))
    assert judge_feed("Fuseau", "https://example.org/feed", 200, soon, NOW).kept
