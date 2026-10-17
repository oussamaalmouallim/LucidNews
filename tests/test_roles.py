"""Roles: with accounts on, a reader reaches only the published news; every other route is for
administrators, whatever the bind address. The route inventory is read from the API's code, so a
route added later without a decision fails here."""

import re
import sqlite3
from pathlib import Path

import pytest

from lucidnews.auth.store import AuthDB
from lucidnews.auth.passwords import hash_password
from lucidnews.web_api import reader_may

from tests.test_auth import PASSWORD, Client, run_cli, start_api

ROOT = Path(__file__).resolve().parents[1]
SUB = "0123456789abcdef"
RUN = "20261013T080000Z-0123abcd"

# Every request the web app can make, with its intended audience.
READER_REQUESTS = [
    ("GET", "/api/health"),
    ("GET", "/api/editions"),
    ("GET", "/api/editions/latest"),
    ("GET", f"/api/editions/{RUN}"),
    ("GET", "/api/editions/period?since=2026-10-01T00:00:00Z&until=2026-10-02T00:00:00Z"),
    ("GET", "/api/items/some-item"),
    ("GET", "/api/search?q=ab"),
]
ADMIN_GETS = [
    "/api/settings",
    "/api/settings/backups",
    "/api/secrets",
    "/api/sources/config",
    "/api/runs",
    "/api/runs/current",
    "/api/schedule",
    "/api/sources?days=14",
    "/api/sources/domains?days=14",
    "/api/coverage?days=14",
    "/api/quality/overview?days=14",
    "/api/catalog",
    "/api/preferences/options",
    "/api/subscribers",
    "/api/deliveries",
    f"/api/subscribers/{SUB}/deliveries",
    f"/api/subscribers/{SUB}/preview",
    "/api/eval/items",
    "/api/eval/report",
]
# Writes an administrator can try without side effects (invalid or unknown targets).
ADMIN_SAFE_WRITES = [
    ("PUT", "/api/settings", {"nope": 1}),
    ("POST", "/api/settings/restore", {}),
    ("POST", "/api/sources/test", {}),
    ("POST", "/api/sources/config", {}),
    ("PUT", "/api/sources/config/unknown", {}),
    ("DELETE", "/api/sources/config/unknown", {}),
    ("PUT", "/api/eval/annotations/unknown", {}),
    ("DELETE", "/api/eval/annotations/unknown", {}),
    ("POST", "/api/subscribers", {"email": "not an address"}),
    ("POST", f"/api/subscribers/{SUB}/confirmation", {}),
    ("PUT", f"/api/subscribers/{SUB}", {}),
    ("DELETE", f"/api/subscribers/{SUB}", {}),
]
# Writes that act (start a pipeline, write the system scheduler): only the refusal is tested.
ADMIN_ACTING_WRITES = [("POST", "/api/runs", {}), ("PUT", "/api/schedule", {})]
ADMIN_REQUESTS = (
    [("GET", path, None) for path in ADMIN_GETS]
    + ADMIN_SAFE_WRITES
    + ADMIN_ACTING_WRITES
    # Deny by default: a reader route written to, or a route nobody declared.
    + [("POST", "/api/editions", {}), ("DELETE", "/api/search", {}), ("GET", "/api/unknown", None)]
)


def code_routes() -> set[str]:
    """Every ``/api/...`` literal the request router tests (the docstring is left out)."""
    source = (ROOT / "lucidnews" / "web_api.py").read_text()
    router = source[source.index("def resolve(") : source.index("def _hostname(")]
    return set(re.findall(r'"(/api/[a-z/_-]*)"', router))


def test_every_route_in_the_code_has_a_declared_audience() -> None:
    declared = [path.split("?")[0] for _, path in READER_REQUESTS] + [path.split("?")[0] for _, path, _ in ADMIN_REQUESTS]
    missing = sorted(route for route in code_routes() if not any(path.startswith(route) for path in declared))
    assert missing == [], f"routes without a test of who may call them: {missing}"


def test_the_reader_list_is_exactly_the_published_news() -> None:
    assert all(reader_may(method, path.split("?")[0]) for method, path in READER_REQUESTS)
    assert not any(reader_may(method, path.split("?")[0]) for method, path, _ in ADMIN_REQUESTS)


@pytest.fixture
def roles(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    ctx, server = start_api(tmp_path, monkeypatch)
    ctx.auth.db.create_user("admin@example.com", "Admin", password_hash=hash_password(PASSWORD), role="admin")
    admin, reader = Client(server), Client(server)
    assert admin.sign_in("admin@example.com")[0] == 200
    assert reader.sign_up()[0] == 201
    yield ctx, server, admin, reader
    server.shutdown()
    server.server_close()


def test_a_reader_is_refused_every_administration_route(roles) -> None:
    _, _, _, reader = roles
    refused = []
    for method, path, body in ADMIN_REQUESTS:
        status, payload, _ = reader.request(method, path, body)
        if (status, payload.get("code")) != (403, "admin_only"):
            refused.append((method, path, status))
    assert refused == [], f"reachable by a reader: {refused}"
    assert len(ADMIN_REQUESTS) >= 30


def test_a_reader_reads_the_published_news(roles) -> None:
    _, _, _, reader = roles
    for method, path in READER_REQUESTS:
        status, _, _ = reader.request(method, path)
        assert status not in (401, 403), (path, status)
    assert reader.request("GET", "/api/editions")[0] == 200
    assert reader.request("GET", "/api/search?q=ab")[0] == 200


def test_an_administrator_reaches_every_route(roles) -> None:
    _, _, admin, _ = roles
    for path in ADMIN_GETS:
        status, _, _ = admin.request("GET", path)
        assert status not in (401, 403), (path, status)
    for method, path, body in ADMIN_SAFE_WRITES:
        status, _, _ = admin.request(method, path, body)
        assert status not in (401, 403), (method, path, status)


def test_a_reader_cannot_read_another_readers_newsletter_preferences(roles) -> None:
    _, _, admin, reader = roles
    status, created, _ = admin.request("POST", "/api/subscribers", {"email": "someone@example.com"})
    assert status == 201
    for path in ("/api/subscribers", f"/api/subscribers/{created['id']}/preview", f"/api/subscribers/{created['id']}/deliveries"):
        assert reader.request("GET", path)[0] == 403
    assert reader.request("PUT", f"/api/subscribers/{created['id']}", {"preferences": {}})[0] == 403
    assert reader.request("DELETE", f"/api/subscribers/{created['id']}", {})[0] == 403
    assert admin.request("GET", "/api/subscribers")[1]["subscribers"][0]["email"] == "someone@example.com"


def test_administration_works_behind_a_reverse_proxy(roles) -> None:
    """The public host name reaches the API (no localhost Host): the role decides, not the address."""
    _, _, admin, reader = roles
    proxied = {"Host": "news.example.com", "Origin": "https://news.example.com"}
    assert admin.request("GET", "/api/settings", headers=proxied)[0] == 200
    assert admin.request("PUT", "/api/settings", {"nope": 1}, headers=proxied)[0] not in (401, 403)
    assert reader.request("GET", "/api/settings", headers=proxied)[0] == 403


def test_an_administrator_write_from_another_site_is_refused(roles) -> None:
    _, _, admin, _ = roles
    status, body, _ = admin.request("PUT", "/api/settings", {"nope": 1}, headers={"Origin": "https://evil.example"})
    assert (status, body["code"]) == (403, "forbidden")


def test_the_session_says_which_role_the_account_has(roles) -> None:
    _, _, admin, reader = roles
    assert admin.request("GET", "/api/auth/session")[1]["user"]["role"] == "admin"
    assert reader.request("GET", "/api/auth/session")[1]["user"]["role"] == "reader"


def test_accounts_made_before_roles_keep_an_owner(tmp_path) -> None:
    """Upgrading: the oldest account (made by the operator) becomes admin, the others readers."""
    path = tmp_path / "auth.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            "CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL,"
            " password_hash TEXT, google_sub TEXT UNIQUE, picture TEXT, created_at TEXT NOT NULL, last_login_at TEXT);"
            "INSERT INTO users VALUES ('b', 'late@example.com', 'Late', 'x', NULL, NULL, '2026-10-02T00:00:00+00:00', NULL);"
            "INSERT INTO users VALUES ('a', 'first@example.com', 'First', 'x', NULL, NULL, '2026-10-01T00:00:00+00:00', NULL);"
        )
    db = AuthDB(path)
    assert {user.email: user.role for user in db.list_users()} == {"first@example.com": "admin", "late@example.com": "reader"}
    AuthDB(path)  # a second start changes nothing
    assert db.count_admins() == 1


def test_administrators_are_made_and_kept_from_the_terminal(tmp_path, monkeypatch, capsys) -> None:
    run = lambda *a, **k: run_cli(tmp_path, monkeypatch, capsys, *a, **k)  # noqa: E731

    assert run("add", "owner@example.com", "--admin", "--password-stdin", stdin=PASSWORD + "\n")[1] == "created owner@example.com (admin)\n"
    assert run("add", "reader@example.com", "--password-stdin", stdin=PASSWORD + "\n")[0] == 0
    assert "\treader\t" in run("list")[1].splitlines()[1]

    # The last administrator can be neither demoted nor removed.
    code, _, err = run("role", "owner@example.com", "reader")
    assert code == 1 and "last administrator" in err
    assert run("remove", "owner@example.com")[0] == 1
    assert run("role", "reader@example.com", "admin")[0] == 0
    assert run("role", "owner@example.com", "reader")[0] == 0
    assert run("role", "nobody@example.com", "admin")[0] == 1
    assert [line.split("\t")[2] for line in run("list")[1].splitlines()] == ["reader", "admin"]
