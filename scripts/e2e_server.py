"""A throwaway API for the end-to-end journeys (lot 31): accounts on, sign-up open, one edition.

The data directory is wiped and rebuilt at every start, so a run never depends on the one before
and never touches ``data/``. Listens on 127.0.0.1 only. The administrator below is a fixture of
this test server, like ``PASSWORD`` in ``tests/test_auth.py``; it exists nowhere else.

    uv run python scripts/e2e_server.py --data-dir /tmp/lucidnews-e2e --port 8766
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from lucidnews.archive import ItemArchive
from lucidnews.auth.passwords import hash_password
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
from lucidnews.web_api import build_context, make_handler

ROOT = Path(__file__).resolve().parent.parent
ADMIN_EMAIL = "admin@e2e.test"
ADMIN_PASSWORD = "e2e admin passphrase"

# (id, domain, score, French title): one news per domain, so "My selection" visibly filters.
NEWS = [
    ("e2e-ai", "ai", 9.5, "Un nouveau modèle de langage ouvert"),
    ("e2e-security", "cybersecurity", 8.5, "Faille critique corrigée dans un serveur web"),
    ("e2e-cloud", "cloud", 7.0, "Nouvelle région cloud en Europe"),
]


def news_item(item_id: str, domain: str, score: float, title: str, now: datetime) -> ContentItem:
    item = ContentItem(
        id=item_id,
        source_type=SourceType.HACKERNEWS,
        title=title,
        url=f"https://example.com/{item_id}",
        published_at=now - timedelta(hours=1),
        processing=ProcessingResult(
            classification=ClassificationResult(profile="tech-news", method="ai_match"),
            analysis=ContentAnalysis(score=score, reason="e2e", summary=title, categories=[domain]),
            artifacts={
                language: ContentArtifact(
                    language=language,
                    title=title,
                    blocks=[ContentBlock(id="summary", title="Résumé", content=f"{title}.", primary=True)],
                )
                for language in ("fr", "en")
            },
        ),
    )
    item.processing.reliability = assess_item(item)
    return item


def prepare(data_dir: Path) -> None:
    shutil.rmtree(data_dir, ignore_errors=True)
    data_dir.mkdir(parents=True)
    config = json.loads((ROOT / "data" / "config.example.json").read_text(encoding="utf-8"))
    config["auth"] = {"enabled": True, "allow_signup": True}
    config["server"] = {"requests_per_minute": 6000}  # the journeys sign in many times a minute
    (data_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    archive = ItemArchive(data_dir / "archive.sqlite3")
    now = datetime.now(timezone.utc)
    run_id = archive.start_run(now - timedelta(hours=24))
    archive.record_items(run_id, [news_item(*news, now) for news in NEWS], selected=True)
    archive.finish_run(run_id, "success")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    os.chdir(ROOT)  # profiles and the source catalog are read relative to the project
    prepare(args.data_dir)
    ctx = build_context(str(args.data_dir), None)
    ctx.auth.db.create_user(ADMIN_EMAIL, "Admin", password_hash=hash_password(ADMIN_PASSWORD), role="admin")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(ctx))
    print(f"LucidNews e2e API on http://127.0.0.1:{args.port} (data: {args.data_dir})", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
