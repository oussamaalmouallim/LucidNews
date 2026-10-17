"""Lot 30 — application security: client address behind a proxy, rate limit, headers, logs,
guessable passwords, absolute session lifetime. The application code under test is the real one."""

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer

import pytest

from lucidnews.auth.passwords import password_problem
from lucidnews.auth.store import AuthDB
from lucidnews.models import ServerConfig
from lucidnews.web_api import build_context, client_ip, make_handler
from tests.test_auth import PASSWORD, ROOT, Client, start_api


# Client address --------------------------------------------------------------------------------


def test_the_client_is_the_peer_unless_a_trusted_proxy_names_it() -> None:
    trusted = frozenset({"127.0.0.1"})
    assert client_ip("198.51.100.7", "203.0.113.9", trusted) == "198.51.100.7"  # an untrusted peer cannot name anyone
    assert client_ip("127.0.0.1", "203.0.113.9", trusted) == "203.0.113.9"
    # A client that sends its own X-Forwarded-For only adds to the left: the proxy's hop is read.
    assert client_ip("127.0.0.1", "10.0.0.1, 203.0.113.9", trusted) == "203.0.113.9"
    assert client_ip("127.0.0.1", "203.0.113.9, 127.0.0.1", trusted) == "203.0.113.9"
    assert client_ip("127.0.0.1", "not-an-ip", trusted) == "127.0.0.1"
    assert client_ip("127.0.0.1", None, trusted) == "127.0.0.1"


def test_trusted_proxies_must_be_ip_addresses() -> None:
    assert ServerConfig(trusted_proxies=[" ::1 ", "127.0.0.1"]).trusted_proxies == ["::1", "127.0.0.1"]
    with pytest.raises(ValueError):
        ServerConfig(trusted_proxies=["proxy.local"])


# Rate limit and headers ------------------------------------------------------------------------


def open_api(tmp_path, monkeypatch, **server):  # type: ignore[no-untyped-def]
    """The API with accounts off (local operator) and the given ``server`` settings."""
    import shutil

    from lucidnews.archive import ItemArchive

    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.json")
    config = json.loads((tmp_path / "config.json").read_text())
    config["server"] = server
    (tmp_path / "config.json").write_text(json.dumps(config))
    ItemArchive(tmp_path / "archive.sqlite3")
    monkeypatch.chdir(ROOT)
    ctx = build_context(str(tmp_path), None, local_features=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ctx))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return ctx, httpd


def test_every_client_is_held_to_a_rate_and_costly_routes_to_a_fifth(tmp_path, monkeypatch) -> None:
    _, httpd = open_api(tmp_path, monkeypatch, requests_per_minute=10)
    try:
        client = Client(httpd)
        searches = [client.request("GET", "/api/search?q=rust")[0] for _ in range(3)]
        assert searches == [200, 200, 429]  # 10 // 5 = 2 searches a minute
        statuses = [client.request("GET", "/api/health")[0] for _ in range(8)]
        assert statuses.count(200) == 7 and statuses[-1] == 429  # 3 + 7 = the 10 of the minute
        status, body, response = client.request("GET", "/api/editions")
        assert (status, body["code"], response.getheader("Retry-After")) == (429, "rate_limited", "60")
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_a_forged_forwarded_header_does_not_escape_the_limit(tmp_path, monkeypatch) -> None:
    _, httpd = open_api(tmp_path, monkeypatch, requests_per_minute=10)
    try:
        client = Client(httpd)
        statuses = [client.request("GET", "/api/health", headers={"X-Forwarded-For": f"203.0.113.{n}"})[0] for n in range(11)]
        assert statuses[-1] == 429
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_behind_a_trusted_proxy_each_visitor_has_their_own_limit(tmp_path, monkeypatch) -> None:
    """Without this, every visitor shares the proxy's address and one of them can lock out all sign-ins."""
    _, httpd = open_api(tmp_path, monkeypatch, requests_per_minute=10, trusted_proxies=["127.0.0.1"])
    try:
        client = Client(httpd)
        first = [client.request("GET", "/api/health", headers={"X-Forwarded-For": "203.0.113.1"})[0] for _ in range(11)]
        assert first[-1] == 429
        assert client.request("GET", "/api/health", headers={"X-Forwarded-For": "203.0.113.2"})[0] == 200
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_every_answer_carries_the_security_headers_and_no_python_version(tmp_path, monkeypatch) -> None:
    ctx, server = start_api(tmp_path, monkeypatch)
    try:
        client = Client(server)
        for path in ("/api/editions", "/api/auth/session"):  # an API answer and an account answer
            _, _, response = client.request("GET", path)
            assert response.getheader("Content-Security-Policy") == "default-src 'none'; frame-ancestors 'none'"
            assert response.getheader("X-Frame-Options") == "DENY"
            assert response.getheader("X-Content-Type-Options") == "nosniff"
            assert response.getheader("Referrer-Policy") == "no-referrer"
            assert response.getheader("Server") == "LucidNews"
    finally:
        server.shutdown()
        server.server_close()


def test_the_logs_never_hold_a_query_string(tmp_path, monkeypatch, capsys) -> None:
    ctx, server = start_api(tmp_path, monkeypatch)
    try:
        Client(server).request("GET", "/api/auth/google/callback?code=secret-code&state=secret-state")
        logged = capsys.readouterr().err
        assert "/api/auth/google/callback" in logged and "secret-code" not in logged and "secret-state" not in logged
    finally:
        server.shutdown()
        server.server_close()


# Passwords ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "password", ["password123", "Azertyuiop", "12345678", "aaaaaaaaaa", "abababab", "qwertyuiop", "poiuytreza", "lucidnews123"]
)
def test_guessable_passwords_are_refused(password) -> None:
    assert password_problem(password) == "too_common"


def test_the_address_itself_is_not_a_password() -> None:
    assert password_problem("ada.lovelace", "ada.lovelace@example.com") == "too_common"
    assert password_problem("ada.lovelace2026", "ada.lovelace@example.com") == "too_common"
    assert password_problem(PASSWORD, "ada.lovelace@example.com") is None


def test_sign_up_and_password_change_explain_a_guessable_password(tmp_path, monkeypatch) -> None:
    ctx, server = start_api(tmp_path, monkeypatch)
    try:
        client = Client(server)
        status, body, _ = client.sign_up(password="password123")
        assert (status, body["code"]) == (422, "common_password")
        assert client.sign_up()[0] == 201
        status, body, _ = client.request("POST", "/api/auth/account/password", {"current": PASSWORD, "password": "reader@example.com"})
        assert (status, body["code"]) == (422, "common_password")
    finally:
        server.shutdown()
        server.server_close()


# Sessions ----------------------------------------------------------------------------------------


def test_a_session_in_use_still_ends_ninety_days_after_the_sign_in(tmp_path) -> None:
    db = AuthDB(tmp_path / "auth.sqlite3")
    user = db.create_user("a@example.com", "A", password_hash="x")
    token = db.create_session(user.id, 30)
    assert db.session_user(token, 30) is not None

    long_ago = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
    with sqlite3.connect(tmp_path / "auth.sqlite3") as conn:
        conn.execute("UPDATE sessions SET created_at = ?", (long_ago,))  # signed in 91 days ago, used yesterday
    assert db.session_user(token, 30) is None
    assert db.session_user(token, 30) is None  # and it was deleted
