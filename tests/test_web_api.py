import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer

from lucidnews.archive import ItemArchive
from lucidnews.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentArtifact,
    ContentBlock,
    ContentItem,
    ProcessingResult,
    SourceType,
)
from lucidnews.reliability.assess import assess_item
from lucidnews.source_quality import item_source_key
from lucidnews.web_api import ApiContext, make_handler, resolve

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def make_item(item_id: str, profile: str, score: float, *, french: bool = True) -> ContentItem:
    artifacts = {
        "en": ContentArtifact(
            language="en",
            title=f"{item_id} EN",
            blocks=[
                ContentBlock(id="summary", title="Summary", content=f"{item_id} summary", primary=True),
                ContentBlock(id="background", title="Background", content="context"),
            ],
        )
    }
    if french:
        artifacts["fr"] = ContentArtifact(
            language="fr",
            title=f"{item_id} FR",
            blocks=[ContentBlock(id="summary", title="Résumé", content=f"{item_id} résumé", primary=True)],
        )
    item = ContentItem(
        id=item_id,
        source_type=SourceType.HACKERNEWS,
        title=f"{item_id} original",
        url=f"https://lwn.net/{item_id}",
        published_at=NOW - timedelta(hours=1),
        metadata={"discussion_url": f"https://news.ycombinator.com/item?id={item_id}"},
        processing=ProcessingResult(
            classification=ClassificationResult(profile=profile, method="ai_match"),
            analysis=ContentAnalysis(score=score, reason="r", summary="analysis summary", categories=["web"]),
            artifacts=artifacts,
        ),
    )
    item.processing.reliability = assess_item(item)
    return item


def make_context(tmp_path) -> tuple[ApiContext, str]:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(hours=24))
    archive.record_items(run_id, [make_item("dropped", "tech-news", 3.0)])
    archive.record_items(
        run_id,
        [
            make_item("blog", "tech-blog", 9.0),
            make_item("low", "tech-news", 7.0, french=False),
            make_item("top", "tech-news", 9.5),
        ],
        selected=True,
    )
    archive.finish_run(run_id, "success")
    ctx = ApiContext(
        archive=archive,
        profile_names={"tech-news": {"default": "Technology News", "fr": "Actualités tech"}},
        profile_order=["tech-news", "tech-blog"],
    )
    return ctx, run_id


def test_latest_edition_groups_selected_items_in_profile_order(tmp_path) -> None:
    ctx, run_id = make_context(tmp_path)

    status, body = resolve(ctx, "/api/editions/latest", {"lang": ["fr"]})

    assert status == 200
    assert (body["id"], body["fetched_count"], body["selected_count"]) == (run_id, 4, 3)
    assert body["available_languages"] == ["en", "fr"]
    assert [(s["profile"], s["name"]) for s in body["sections"]] == [
        ("tech-news", "Actualités tech"),
        ("tech-blog", "Tech Blog"),
    ]
    top, low = body["sections"][0]["items"]
    assert (top["title"], top["summary"], top["importance"]) == ("top FR", "top résumé", "critical")
    assert top["reliability"]["label"] == "reliable"
    assert top["discussion_url"] == "https://news.ycombinator.com/item?id=top"
    # No French artifact: original title and analysis summary, flagged as untranslated.
    assert (low["title"], low["summary"], low["translated"]) == ("low original", "analysis summary", False)


def test_edition_by_id_and_errors(tmp_path) -> None:
    ctx, run_id = make_context(tmp_path)

    status, body = resolve(ctx, f"/api/editions/{run_id}", {})
    assert status == 200
    assert body["sections"][0]["items"][0]["sections"] == [
        {"id": "background", "title": "Background", "content": "context"}
    ]
    assert resolve(ctx, "/api/editions", {})[1]["editions"][0]["id"] == run_id
    assert resolve(ctx, "/api/editions/../../etc", {})[0] == 400
    assert resolve(ctx, "/api/editions/20990101T000000Z-00000000", {})[0] == 404
    assert resolve(ctx, "/api/editions/latest", {"lang": ["xx"]})[0] == 400
    assert resolve(ctx, "/api/unknown", {})[0] == 404


def test_http_server_serves_json(tmp_path) -> None:
    ctx, _ = make_context(tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ctx))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/api/editions/latest?lang=fr") as response:
            assert response.headers["Content-Type"] == "application/json; charset=utf-8"
            assert json.loads(response.read())["sections"][0]["name"] == "Actualités tech"
        try:
            urllib.request.urlopen(f"{base}/api/nope")
        except urllib.error.HTTPError as error:
            assert error.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_sources_endpoint_reports_configured_sources_and_runs(tmp_path) -> None:
    from lucidnews.source_health import SourceRunOutcome

    ctx, run_id = make_context(tmp_path)
    ctx.configured_sources = {"rss/Kept": "rss", "rss/New": "rss"}
    ctx.archive.record_source_runs(
        run_id,
        [
            SourceRunOutcome("rss/Kept", "rss", "failure", error="HTTPStatusError: 404"),
            SourceRunOutcome("rss/Removed", "rss", "success", fetched_count=4),
        ],
    )

    status, body = resolve(ctx, "/api/sources", {"days": ["7"]})

    assert status == 200
    assert [(s["source"], s["status"], s["last_error"]) for s in body["sources"]] == [
        ("rss/Kept", "failing", "HTTPStatusError: 404")
    ]
    assert body["configured_without_history"] == ["rss/New"]
    assert [(r["id"], r["fetched_count"], r["selected_count"]) for r in body["runs"]] == [(run_id, 4, 3)]
    assert resolve(ctx, "/api/sources", {"days": ["0"]})[0] == 400
    assert resolve(ctx, "/api/sources", {"days": ["abc"]})[0] == 400


def test_item_detail_returns_claim_and_publishing_editions(tmp_path) -> None:
    ctx, run_id = make_context(tmp_path)

    status, body = resolve(ctx, "/api/items/top", {"lang": ["fr"]})

    assert status == 200
    assert (body["title"], body["language"], body["profile_name"]) == ("top FR", "fr", "Actualités tech")
    assert body["available_languages"] == ["en", "fr"]
    assert [edition["id"] for edition in body["editions"]] == [run_id]
    assert body["claim"] is None
    # Not selected in any run: no edition listed, still readable.
    assert resolve(ctx, "/api/items/dropped", {})[1]["editions"] == []


def test_item_detail_decodes_ids_and_rejects_bad_ones(tmp_path) -> None:
    ctx, _ = make_context(tmp_path)
    item = make_item("hackernews:story:42", "tech-news", 8.0)
    ctx.archive.record_items(ctx.archive.list_runs()[0].id, [item])

    assert resolve(ctx, "/api/items/hackernews%3Astory%3A42", {})[1]["id"] == "hackernews:story:42"
    assert resolve(ctx, "/api/items/missing", {})[0] == 404
    assert resolve(ctx, "/api/items/bad%0Aid", {})[0] == 400


def _dated_run(archive, started_at: str, items) -> str:
    run_id = archive.start_run(NOW - timedelta(hours=24))
    archive.record_items(run_id, items, selected=True)
    archive.finish_run(run_id, "success")
    import sqlite3

    with sqlite3.connect(archive.path) as conn:
        conn.execute("UPDATE runs SET started_at = ? WHERE id = ?", (started_at, run_id))
    return run_id


def test_period_merges_the_editions_started_inside_it(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    _dated_run(archive, "2026-09-30T06:00:00+00:00", [make_item("sept", "tech-news", 9.9)])
    _dated_run(archive, "2026-10-02T06:00:00+00:00", [make_item("shared", "tech-news", 8.0), make_item("a", "tech-news", 6.0)])
    _dated_run(archive, "2026-10-03T06:00:00+00:00", [make_item("shared", "tech-news", 8.0), make_item("b", "tech-blog", 9.0)])
    _dated_run(archive, "2026-11-01T06:00:00+00:00", [make_item("nov", "tech-news", 9.9)])
    ctx = ApiContext(archive=archive, profile_order=["tech-news", "tech-blog"])

    status, body = resolve(ctx, "/api/editions/period", {"since": ["2026-10-01T00:00:00Z"], "until": ["2026-11-01T00:00:00Z"], "lang": ["fr"]})

    assert status == 200
    assert body["edition_count"] == 2 and body["id"] == "period"
    ids = [item["id"] for section in body["sections"] for item in section["items"]]
    assert sorted(ids) == ["a", "b", "shared"]  # September and November are outside; "shared" once
    assert [section["profile"] for section in body["sections"]] == ["tech-news", "tech-blog"]
    assert body["selected_count"] == 3 and body["analyzed_total"] == 3

    # The bounds are half-open: an edition starting exactly at `until` is out.
    day = resolve(ctx, "/api/editions/period", {"since": ["2026-10-02T06:00:00Z"], "until": ["2026-10-03T06:00:00Z"]})[1]
    assert day["edition_count"] == 1 and day["selected_count"] == 2

    empty = resolve(ctx, "/api/editions/period", {"since": ["2025-01-01T00:00:00Z"], "until": ["2026-01-01T00:00:00Z"]})[1]
    assert empty["edition_count"] == 0 and empty["sections"] == []


def test_period_lists_every_news_without_any_limit(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    _dated_run(archive, "2026-10-02T06:00:00+00:00", [make_item(f"i{n}", "tech-news", 1.0 + n / 20) for n in range(150)])
    ctx = ApiContext(archive=archive)

    body = resolve(ctx, "/api/editions/period", {"since": ["2026-10-01T00:00:00Z"], "until": ["2026-10-31T00:00:00Z"]})[1]

    ids = [item["id"] for item in body["sections"][0]["items"]]
    assert len(ids) == 150 and ids[0] == "i149" and ids[-1] == "i0"  # best score first
    assert body["analyzed_total"] == 150
    assert "listed_limit" not in body


def test_period_and_limit_reject_bad_input(tmp_path) -> None:
    ctx = ApiContext(archive=ItemArchive(tmp_path / "archive.sqlite3"))
    ok = "2026-10-01T00:00:00Z"

    assert resolve(ctx, "/api/editions/period", {})[0] == 400
    assert resolve(ctx, "/api/editions/period", {"since": ["nope"], "until": [ok]})[0] == 400
    assert resolve(ctx, "/api/editions/period", {"since": [ok], "until": [ok]})[0] == 400
    assert resolve(ctx, "/api/editions/period", {"since": [ok], "until": ["2099-01-01T00:00:00Z"]})[0] == 400
    assert resolve(ctx, "/api/editions", {"limit": ["0"]})[0] == 400
    assert resolve(ctx, "/api/editions", {"limit": ["x"]})[0] == 400
    assert resolve(ctx, "/api/editions", {"limit": ["500"]})[0] == 200


def test_source_domains_use_the_archive_then_the_catalog(tmp_path) -> None:
    from lucidnews.source_catalog import CatalogEntry

    archive = ItemArchive(tmp_path / "archive.sqlite3")
    ai_items = [make_item(f"ai{n}", "tech-news", 8.0) for n in range(3)]
    for item in ai_items:
        item.processing.analysis.categories = ["ai", "web"]
    web_item = make_item("web1", "tech-news", 8.0)
    web_item.processing.analysis.categories = ["web"]
    _dated_run(archive, "2026-10-02T06:00:00+00:00", ai_items + [web_item])
    key = item_source_key(ai_items[0])
    catalog = [
        CatalogEntry("rss/Declared", "rss", "Declared", "databases", {}, None, "example"),
        CatalogEntry(key, "rss", "Same key", "cloud", {}, None, "example"),  # the archive wins over the catalog
    ]
    ctx = ApiContext(
        archive=archive,
        catalog=catalog,
        configured_sources={key: "hackernews", "rss/Declared": "rss", "rss/Unknown": "rss"},
    )

    status, body = resolve(ctx, "/api/sources/domains", {"days": ["90"]})

    assert status == 200
    domains = body["domains"]
    # "web" is on 4 analyzed items, "ai" on 3: the most frequent one is the domain.
    assert domains[key]["category"] == "web" and domains[key]["origin"] == "archive"
    assert domains[key]["categories"] == [{"category": "web", "items": 4}, {"category": "ai", "items": 3}]
    assert domains["rss/Declared"] == {"category": "databases", "origin": "catalog", "categories": []}
    assert domains["rss/Unknown"] == {"category": None, "origin": None, "categories": []}
    # A source that is not configured any more still gets its domain (the interface may list it).
    ctx.configured_sources = {}
    assert resolve(ctx, "/api/sources/domains", {"days": ["90"]})[1]["domains"][key]["category"] == "web"
    assert resolve(ctx, "/api/sources/domains", {"days": ["0"]})[0] == 400
