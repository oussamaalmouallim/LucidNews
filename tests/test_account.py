"""The signed-in person's own account (lot 28): name, password, open sessions, export, deletion.
No e-mail is involved. The application code under test is the real one."""

import json

import pytest

from lucidnews.auth.passwords import hash_password
from lucidnews.auth.service import device_label
from tests.test_auth import PASSWORD, Client, start_api

FIREFOX_MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:131.0) Gecko/20100101 Firefox/131.0"
CHROME_ANDROID = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"


@pytest.fixture
def account(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    ctx, server = start_api(tmp_path, monkeypatch)
    ctx.auth.db.create_user("owner@example.com", "Owner", password_hash=hash_password(PASSWORD), role="admin")
    client = Client(server)
    assert client.sign_up()[0] == 201  # reader@example.com
    yield ctx, server, client
    server.shutdown()
    server.server_close()


def browser(server, user_agent=FIREFOX_MAC, email="reader@example.com"):  # type: ignore[no-untyped-def]
    other = Client(server)
    status, _, _ = other.request("POST", "/api/auth/sign-in", {"email": email, "password": PASSWORD}, headers={"User-Agent": user_agent})
    assert status == 200
    return other


def test_the_device_is_named_without_keeping_the_raw_user_agent() -> None:
    assert device_label(FIREFOX_MAC) == "Firefox · macOS"
    assert device_label(CHROME_ANDROID) == "Chrome · Android"
    assert device_label("curl/8.4") is None and device_label(None) is None


def test_the_account_page_needs_a_session(account) -> None:
    _, server, _ = account
    stranger = Client(server)
    for method, path in (("GET", "/api/auth/account"), ("PUT", "/api/auth/account"), ("GET", "/api/auth/account/export"), ("POST", "/api/auth/account/delete")):
        assert stranger.request(method, path, {})[1]["code"] == "unauthenticated", path


def test_a_reader_renames_themselves_and_sees_their_sessions(account) -> None:
    _, server, client = account
    browser(server, FIREFOX_MAC)

    status, body, _ = client.request("PUT", "/api/auth/account", {"name": "  Ada  "})
    assert status == 200 and body["user"]["name"] == "Ada"
    assert client.request("PUT", "/api/auth/account", {"name": " "})[1]["code"] == "invalid_name"

    sessions = client.request("GET", "/api/auth/account")[1]["sessions"]
    assert len(sessions) == 2
    assert [session["current"] for session in sessions].count(True) == 1
    assert "Firefox · macOS" in [session["device"] for session in sessions]
    assert all(len(session["id"]) == 16 for session in sessions)


def test_one_session_or_all_others_can_be_closed_but_not_the_current_one(account) -> None:
    _, server, client = account
    phone, laptop = browser(server, CHROME_ANDROID), browser(server, FIREFOX_MAC)
    sessions = client.request("GET", "/api/auth/account")[1]["sessions"]
    current = next(session["id"] for session in sessions if session["current"])
    phone_id = next(session["id"] for session in sessions if session["device"] == "Chrome · Android")

    assert client.request("DELETE", f"/api/auth/account/sessions/{current}", {})[1]["code"] == "current_session"
    assert client.request("DELETE", f"/api/auth/account/sessions/{phone_id}", {})[0] == 200
    assert phone.request("GET", "/api/editions")[0] == 401
    assert laptop.request("GET", "/api/editions")[0] == 200
    assert client.request("DELETE", "/api/auth/account/sessions/zzzz", {})[0] == 404

    assert client.request("POST", "/api/auth/account/sessions/close-others", {})[1]["closed"] == 1
    assert laptop.request("GET", "/api/editions")[0] == 401
    assert client.request("GET", "/api/editions")[0] == 200


def test_a_reader_cannot_close_someone_elses_session(account) -> None:
    _, server, client = account
    owner = browser(server, email="owner@example.com")
    owner_id = next(s["id"] for s in owner.request("GET", "/api/auth/account")[1]["sessions"] if s["current"])

    assert client.request("DELETE", f"/api/auth/account/sessions/{owner_id}", {})[0] == 404
    assert owner.request("GET", "/api/settings")[0] == 200


def test_changing_the_password_needs_the_current_one_and_ends_the_other_sessions(account) -> None:
    _, server, client = account
    other = browser(server)

    assert client.request("POST", "/api/auth/account/password", {"current": "wrong", "password": "a new long password"})[1]["code"] == "wrong_password"
    assert client.request("POST", "/api/auth/account/password", {"current": PASSWORD, "password": "short"})[1]["code"] == "weak_password"
    assert client.request("POST", "/api/auth/account/password", {"current": PASSWORD, "password": "a new long password"})[0] == 200

    assert client.request("GET", "/api/editions")[0] == 200  # this session stays
    assert other.request("GET", "/api/editions")[0] == 401  # the others end
    assert Client(server).sign_in(password="a new long password")[0] == 200
    assert Client(server).sign_in()[0] == 401


def test_current_password_checks_are_rate_limited(account) -> None:
    _, _, client = account
    codes = [client.request("POST", "/api/auth/account/password", {"current": "wrong", "password": "a new long password"})[1]["code"] for _ in range(9)]
    assert codes[:8] == ["wrong_password"] * 8 and codes[8] == "rate_limited"


def test_the_export_holds_the_persons_data_and_no_secret(account) -> None:
    ctx, server, client = account
    browser(server)
    status, export, _ = client.request("GET", "/api/auth/account/export")

    assert status == 200 and export["format"] == "lucidnews-account-export/1"
    assert export["account"]["email"] == "reader@example.com" and export["account"]["role"] == "reader"
    assert export["account"]["sign_in_methods"] == ["password"] and export["account"]["created_at"]
    assert len(export["sessions"]) == 2 and "id" not in export["sessions"][0]
    raw = json.dumps(export)
    stored = ctx.auth.db.password_hash(ctx.auth.db.by_email("reader@example.com")[0].id)
    assert stored not in raw and "scrypt" not in raw and client.cookies["lucidnews_session"] not in raw


def test_deleting_the_account_needs_the_password_and_signs_out_everywhere(account) -> None:
    ctx, server, client = account
    other = browser(server)

    assert client.request("POST", "/api/auth/account/delete", {"current": "wrong"})[1]["code"] == "wrong_password"
    status, body, _ = client.request("POST", "/api/auth/account/delete", {"current": PASSWORD})
    assert status == 200 and body["authenticated"] is False
    assert "lucidnews_session" not in client.cookies

    assert ctx.auth.db.by_email("reader@example.com") is None
    assert other.request("GET", "/api/editions")[0] == 401
    assert Client(server).sign_in()[0] == 401


def test_a_google_account_confirms_deletion_by_typing_its_address(account) -> None:
    ctx, server, _ = account
    user = ctx.auth.db.create_user("g@example.com", "G", google_sub="google-1")
    client = Client(server)
    client.cookies["lucidnews_session"] = ctx.auth.db.create_session(user.id, 30)

    assert client.request("POST", "/api/auth/account/delete", {"email": "other@example.com"})[1]["code"] == "confirm_email"
    assert client.request("POST", "/api/auth/account/delete", {"email": "G@Example.com"})[0] == 200
    assert ctx.auth.db.by_email("g@example.com") is None


def test_the_last_administrator_cannot_delete_their_account(account) -> None:
    _, server, _ = account
    owner = browser(server, email="owner@example.com")
    assert owner.request("GET", "/api/auth/account")[1]["can_delete"] is False
    assert owner.request("POST", "/api/auth/account/delete", {"current": PASSWORD})[1]["code"] == "last_admin"


def test_account_writes_from_another_site_are_refused(account) -> None:
    _, _, client = account
    status, body, _ = client.request("PUT", "/api/auth/account", {"name": "Mallory"}, headers={"Origin": "https://evil.example"})
    assert (status, body["code"]) == (403, "forbidden")
    assert client.request("POST", "/api/auth/account/delete", {"current": PASSWORD}, headers={"Origin": "https://evil.example"})[0] == 403
