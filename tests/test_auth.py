"""Accounts: sign up and in with e-mail, Google OAuth (against a local stand-in for Google's
token endpoint), sessions, route protection. The application code under test is the real one."""

import base64
import http.client
import json
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from lucidnews.archive import ItemArchive
from lucidnews.auth.google import GoogleOAuth
from lucidnews.auth.passwords import hash_password, password_problem, verify_password
from lucidnews.auth.service import AuthService, RateLimiter, safe_next
from lucidnews.auth.store import AuthDB
from lucidnews.models import AuthConfig
from lucidnews.web_api import build_context, make_handler

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "correct horse battery"


# Passwords ------------------------------------------------------------------------------------


def test_passwords_are_salted_and_verified_in_constant_form() -> None:
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)

    assert first != second and PASSWORD not in first
    assert verify_password(PASSWORD, first) and not verify_password("wrong", first)
    assert not verify_password(PASSWORD, "not a hash") and not verify_password(PASSWORD, "scrypt$1$2")


@pytest.mark.parametrize("password,reason", [("short", "too_short"), ("x" * 200, "too_long"), (None, "required"), (12345678, "required")])
def test_password_rules(password, reason) -> None:
    assert password_problem(password) == reason
    assert password_problem(PASSWORD) is None


def test_next_path_can_only_stay_on_this_site() -> None:
    assert safe_next("/archive?q=a") == "/archive?q=a"
    for bad in ("https://evil.example", "//evil.example", "/\\evil", "javascript:alert(1)", "", None, "/api/auth/sign-out", "/sign-in"):
        assert safe_next(bad) == "/"


def test_rate_limiter_blocks_then_recovers() -> None:
    now = [0.0]
    limiter = RateLimiter(2, 10, clock=lambda: now[0])
    assert limiter.hit("a") and limiter.hit("a") and not limiter.hit("a")
    assert limiter.hit("b")
    now[0] = 11
    assert limiter.hit("a")


# Store ----------------------------------------------------------------------------------------


def test_sessions_are_stored_hashed_expire_and_slide(tmp_path) -> None:
    db = AuthDB(tmp_path / "auth.sqlite3")
    user = db.create_user("a@example.com", "A", password_hash="x")
    assert db.create_user("A@EXAMPLE.COM", "Again") is None  # addresses are case-insensitive

    token = db.create_session(user.id, 30)
    assert db.session_user(token, 30).id == user.id
    assert db.session_user("nope", 30) is None
    assert token.encode() not in (tmp_path / "auth.sqlite3").read_bytes()

    import sqlite3

    with sqlite3.connect(tmp_path / "auth.sqlite3") as conn:
        conn.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00+00:00'")
    assert db.session_user(token, 30) is None
    assert db.session_user(token, 30) is None  # and it was deleted


# HTTP -----------------------------------------------------------------------------------------


class FakeGoogle:
    """Stands in for accounts.google.com's token endpoint. Answers like Google does, with whatever
    claims the test sets; the nonce comes from the authorization request the app made."""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.claims: dict = {}
        self.requests: list = []
        self.status = 200
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                form = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
                fake.requests.append({key: value[0] for key, value in form.items()})
                claims = {"iss": "https://accounts.google.com", "aud": fake.client_id, "exp": time.time() + 600, "email_verified": True, **fake.claims}
                payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
                body = json.dumps({"id_token": f"h.{payload}.s", "access_token": "unused"}).encode()
                self.send_response(fake.status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):  # noqa: D102
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/token"

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def google():
    fake = FakeGoogle("client-123")
    yield fake
    fake.stop()


def start_api(tmp_path, monkeypatch, google_fake=None, **auth):  # type: ignore[no-untyped-def]
    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.json")
    config = json.loads((tmp_path / "config.json").read_text())
    config["auth"] = {"enabled": True, **auth}
    (tmp_path / "config.json").write_text(json.dumps(config))
    ItemArchive(tmp_path / "archive.sqlite3")
    monkeypatch.chdir(ROOT)
    for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    if google_fake is not None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-123")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "the-secret")
    ctx = build_context(str(tmp_path), None, local_features=True)
    if google_fake is not None:
        ctx.auth.google.token_url = google_fake.url
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ctx))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return ctx, server


class Client:
    """A browser: keeps cookies, sends the Origin a browser would."""

    def __init__(self, server):  # type: ignore[no-untyped-def]
        self.port = server.server_address[1]
        self.cookies: dict[str, str] = {}

    def request(self, method, path, body=None, headers=None):  # type: ignore[no-untyped-def]
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        base = {"Origin": f"http://127.0.0.1:{self.port}", "Content-Type": "application/json"}
        if self.cookies:
            base["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        conn.request(method, path, body=json.dumps(body) if body is not None else None, headers={**base, **(headers or {})})
        response = conn.getresponse()
        raw = response.read()
        for header, value in response.getheaders():
            if header.lower() == "set-cookie":
                name, _, rest = value.partition("=")
                content = rest.split(";")[0]
                if "Max-Age=0" in value:
                    self.cookies.pop(name, None)
                else:
                    self.cookies[name] = content
        conn.close()
        return response.status, (json.loads(raw) if raw else {}), response

    def sign_up(self, email="reader@example.com", password=PASSWORD, **extra):  # type: ignore[no-untyped-def]
        return self.request("POST", "/api/auth/sign-up", {"email": email, "password": password, **extra})

    def sign_in(self, email="reader@example.com", password=PASSWORD):  # type: ignore[no-untyped-def]
        return self.request("POST", "/api/auth/sign-in", {"email": email, "password": password})


@pytest.fixture
def api(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    ctx, server = start_api(tmp_path, monkeypatch)
    yield ctx, server, Client(server)
    server.shutdown()
    server.server_close()


def test_without_accounts_nothing_changes(tmp_path, monkeypatch) -> None:
    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.json")
    ItemArchive(tmp_path / "archive.sqlite3")
    monkeypatch.chdir(ROOT)
    ctx = build_context(str(tmp_path), None, local_features=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ctx))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = Client(server)
    try:
        assert ctx.auth is None and not (tmp_path / "auth.sqlite3").exists()
        assert client.request("GET", "/api/auth/session")[1] == {"enabled": False, "authenticated": False, "user": None, "signup_enabled": False, "providers": {"google": False}}
        assert client.request("POST", "/api/auth/sign-in", {"email": "a@b.co", "password": PASSWORD})[0] == 404
        assert client.request("GET", "/api/settings")[0] == 200
    finally:
        server.shutdown()
        server.server_close()


def test_every_api_route_needs_a_session_once_accounts_are_on(api) -> None:
    _, _, client = api
    for path in ("/api/editions", "/api/settings", "/api/sources", "/api/search?q=ab"):
        status, body, _ = client.request("GET", path)
        assert (status, body["code"]) == (401, "unauthenticated"), path
    assert client.request("PUT", "/api/settings", {})[0] == 401
    assert client.request("GET", "/api/auth/session")[1]["authenticated"] is False


def test_sign_up_signs_in_without_any_e_mail_step_and_the_session_persists(api) -> None:
    ctx, server, client = api

    status, body, response = client.sign_up(name="  Reader  ")

    assert status == 201 and body["authenticated"] is True
    assert body["user"]["email"] == "reader@example.com" and body["user"]["name"] == "Reader"
    assert PASSWORD not in json.dumps(body) and "scrypt" not in json.dumps(body) and "google_sub" not in json.dumps(body)
    cookie = response.getheader("Set-Cookie")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Max-Age=2592000" in cookie and "Secure" not in cookie
    assert client.request("GET", "/api/editions")[0] == 200  # the protected routes open

    again = Client(server)  # a new browser has no session; one holding the cookie does
    assert again.request("GET", "/api/editions")[0] == 401
    again.cookies = dict(client.cookies)
    assert again.request("GET", "/api/auth/session")[1]["user"]["email"] == "reader@example.com"
    assert ctx.auth.db.by_email("reader@example.com")[1].startswith("scrypt$")


def test_sign_out_ends_the_session_on_the_server(api) -> None:
    _, server, client = api
    client.sign_up()
    stolen = dict(client.cookies)

    status, body, _ = client.request("POST", "/api/auth/sign-out")

    assert status == 200 and body["authenticated"] is False and client.cookies == {}
    thief = Client(server)
    thief.cookies = stolen
    assert thief.request("GET", "/api/editions")[0] == 401  # the old cookie is dead, not just forgotten


@pytest.mark.parametrize(
    "body,code",
    [
        ({"email": "nope", "password": PASSWORD}, "invalid_email"),
        ({"email": "a@b", "password": PASSWORD}, "invalid_email"),
        ({"email": "a@example.com", "password": "short"}, "weak_password"),
        ({"email": ["a@example.com"], "password": PASSWORD}, "invalid_email"),
    ],
)
def test_sign_up_validates_input(api, body, code) -> None:
    status, payload, _ = api[2].request("POST", "/api/auth/sign-up", body)
    assert status == 422 and payload["code"] == code


def test_an_address_can_only_register_once(api) -> None:
    client = api[2]
    assert client.sign_up()[0] == 201
    status, body, _ = Client(api[1]).sign_up(email="READER@example.com")
    assert (status, body["code"]) == (409, "email_taken")


def test_sign_in_gives_the_same_answer_for_a_wrong_password_and_an_unknown_address(api) -> None:
    _, server, client = api
    client.sign_up()
    other = Client(server)

    wrong = other.sign_in(password="not the password")
    unknown = other.sign_in(email="ghost@example.com")

    assert wrong[0] == unknown[0] == 401 and wrong[1] == unknown[1] and wrong[1]["code"] == "invalid_credentials"
    assert other.cookies == {}
    assert other.sign_in()[0] == 200 and other.request("GET", "/api/editions")[0] == 200


def test_repeated_failures_are_rate_limited(api) -> None:
    _, server, client = api
    client.sign_up()
    other = Client(server)
    codes = [other.sign_in(password=f"wrong password {i}")[1]["code"] for i in range(10)]

    assert codes[:8] == ["invalid_credentials"] * 8 and codes[8] == "rate_limited"
    assert other.sign_in()[0] == 429  # even the right password waits


def test_a_cross_site_form_cannot_sign_anyone_in_or_out(api) -> None:
    _, _, client = api
    status, body, _ = client.request("POST", "/api/auth/sign-up", {"email": "x@example.com", "password": PASSWORD}, {"Origin": "https://evil.example"})
    assert (status, body["code"]) == (403, "forbidden")
    status, _, _ = client.request("POST", "/api/auth/sign-in", {"email": "x@example.com", "password": PASSWORD}, {"Content-Type": "text/plain"})
    assert status == 415


def test_sign_up_can_be_closed(tmp_path, monkeypatch) -> None:
    ctx, server = start_api(tmp_path, monkeypatch, allow_signup=False)
    try:
        status, body, _ = Client(server).sign_up()
        assert (status, body["code"]) == (403, "signup_disabled")
        assert Client(server).request("GET", "/api/auth/session")[1]["signup_enabled"] is False
    finally:
        server.shutdown()
        server.server_close()


# Google ---------------------------------------------------------------------------------------


@pytest.fixture
def with_google(tmp_path, monkeypatch, google):  # type: ignore[no-untyped-def]
    ctx, server = start_api(tmp_path, monkeypatch, google_fake=google)
    yield ctx, server, Client(server), google
    server.shutdown()
    server.server_close()


def begin(client: Client, next_path: str = "/archive") -> dict:
    status, _, response = client.request("GET", f"/api/auth/google/start?next={next_path}")
    assert status == 302
    return {key: value[0] for key, value in parse_qs(urlsplit(response.getheader("Location")).query).items()}


def finish(client: Client, query: dict, **override):  # type: ignore[no-untyped-def]
    params = {"code": "auth-code", "state": query["state"], **override}
    path = "/api/auth/google/callback?" + "&".join(f"{k}={v}" for k, v in params.items())
    status, _, response = client.request("GET", path)
    return status, response.getheader("Location")


def test_google_is_offered_only_when_it_is_configured(api, with_google) -> None:
    assert api[2].request("GET", "/api/auth/session")[1]["providers"] == {"google": False}
    assert with_google[2].request("GET", "/api/auth/session")[1]["providers"] == {"google": True}
    status, _, response = api[2].request("GET", "/api/auth/google/start")
    assert status == 302 and response.getheader("Location") == "/sign-in?error=google_unavailable"


def test_google_sign_in_creates_an_account_and_a_session(with_google) -> None:
    ctx, _, client, google = with_google
    query = begin(client)

    assert query["client_id"] == "client-123" and query["response_type"] == "code" and query["scope"] == "openid email profile"
    assert query["code_challenge_method"] == "S256" and len(query["code_challenge"]) == 43
    assert query["redirect_uri"] == f"http://127.0.0.1:{client.port}/api/auth/google/callback"
    google.claims = {"sub": "g-1", "email": "Reader@Example.com", "name": "Ada Reader", "nonce": query["nonce"], "picture": "https://lh3.example/a.png"}

    status, location = finish(client, query)

    assert (status, location) == (302, "/archive")
    exchange = google.requests[0]
    assert exchange["grant_type"] == "authorization_code" and exchange["client_secret"] == "the-secret" and exchange["code"] == "auth-code"
    assert exchange["redirect_uri"] == query["redirect_uri"] and len(exchange["code_verifier"]) >= 43
    state = client.request("GET", "/api/auth/session")[1]
    assert state["authenticated"] and state["user"]["email"] == "reader@example.com" and state["user"]["has_google"] and not state["user"]["has_password"]
    assert client.request("GET", "/api/editions")[0] == 200


def test_google_callback_refuses_a_forged_or_replayed_return(with_google) -> None:
    _, server, client, google = with_google
    query = begin(client)
    google.claims = {"sub": "g-1", "email": "reader@example.com", "nonce": query["nonce"]}

    attacker_browser = Client(server)  # lacks the cookie that started the flow
    assert finish(attacker_browser, query) == (302, "/sign-in?error=state_invalid")
    assert finish(client, query) == (302, "/sign-in?error=state_invalid")  # the state was used up by the first try
    assert finish(client, {"state": "made-up"}) == (302, "/sign-in?error=state_invalid")
    assert client.request("GET", "/api/auth/session")[1]["authenticated"] is False


@pytest.mark.parametrize(
    "claims,code",
    [
        ({"aud": "someone-else"}, "invalid_token"),
        ({"iss": "https://evil.example"}, "invalid_token"),
        ({"exp": 1}, "invalid_token"),
        ({"nonce": "other"}, "invalid_token"),
        ({"email_verified": False}, "email_not_verified"),
        ({"email": ""}, "invalid_token"),
    ],
)
def test_google_id_token_is_validated(with_google, claims, code) -> None:
    _, _, client, google = with_google
    query = begin(client)
    google.claims = {"sub": "g-1", "email": "reader@example.com", "nonce": query["nonce"], **claims}

    assert finish(client, query) == (302, f"/sign-in?error={code}")
    assert client.cookies.get("lucidnews_session") is None


def test_google_errors_never_open_a_session(with_google) -> None:
    _, _, client, google = with_google
    google.status = 400
    assert finish(client, begin(client)) == (302, "/sign-in?error=token_exchange_failed")
    assert finish(client, begin(client), error="access_denied") == (302, "/sign-in?error=google_cancelled")


def test_google_takes_over_a_password_account_because_its_address_was_never_verified(with_google) -> None:
    ctx, server, client, google = with_google
    squatter = Client(server)
    squatter.sign_up(email="victim@example.com", password="attacker chosen password")
    assert squatter.request("GET", "/api/editions")[0] == 200

    query = begin(client)
    google.claims = {"sub": "g-victim", "email": "victim@example.com", "name": "Victim", "nonce": query["nonce"]}
    assert finish(client, query) == (302, "/archive")

    assert client.request("GET", "/api/editions")[0] == 200  # the real owner is in
    assert squatter.request("GET", "/api/editions")[0] == 401  # the squatter's session ended
    assert Client(server).sign_in("victim@example.com", "attacker chosen password")[1]["code"] == "use_google"
    assert ctx.auth.db.by_email("victim@example.com")[1] is None


def test_google_respects_closed_sign_up_for_new_addresses(tmp_path, monkeypatch, google) -> None:
    ctx, server = start_api(tmp_path, monkeypatch, google_fake=google, allow_signup=False)
    client = Client(server)
    try:
        query = begin(client)
        google.claims = {"sub": "g-2", "email": "new@example.com", "nonce": query["nonce"]}
        assert finish(client, query) == (302, "/sign-in?error=signup_disabled")
    finally:
        server.shutdown()
        server.server_close()


def test_a_public_https_url_makes_cookies_secure_and_names_the_redirect_uri(tmp_path, monkeypatch, google) -> None:
    ctx, server = start_api(tmp_path, monkeypatch, google_fake=google, public_url="https://news.example.com/")
    client = Client(server)
    try:
        assert ctx.auth.config.public_url == "https://news.example.com"
        _, _, response = client.request(
            "POST", "/api/auth/sign-up", {"email": "s@example.com", "password": PASSWORD}, {"Origin": "https://news.example.com"}
        )
        assert "Secure" in response.getheader("Set-Cookie")
        query = begin(client)
        assert query["redirect_uri"] == "https://news.example.com/api/auth/google/callback"
    finally:
        server.shutdown()
        server.server_close()


def test_the_host_header_is_not_trusted_to_build_the_redirect_uri_off_localhost(tmp_path) -> None:
    config = AuthConfig(enabled=True)
    service = AuthService(config, AuthDB(tmp_path / "auth.sqlite3"), google=GoogleOAuth("c", "s"))
    assert service._base_url({"Host": "evil.example"}) is None
    assert service._base_url({"Host": "localhost:5173"}) == "http://localhost:5173"


def test_auth_settings_are_validated() -> None:
    assert AuthConfig(public_url="http://localhost:5173/").public_url == "http://localhost:5173"
    for bad in ("ftp://x.example", "https://x.example/path", "https://x.example?a=1", "not a url"):
        with pytest.raises(ValueError):
            AuthConfig(public_url=bad)


# Terminal ---------------------------------------------------------------------------------------


def run_cli(tmp_path, monkeypatch, capsys, *argv, stdin=""):  # type: ignore[no-untyped-def]
    import io

    from lucidnews.auth.cli import main

    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = main(["--data-dir", str(tmp_path), *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_accounts_can_be_managed_from_the_terminal_while_sign_up_is_closed(tmp_path, monkeypatch, capsys) -> None:
    run = lambda *a, **k: run_cli(tmp_path, monkeypatch, capsys, *a, **k)  # noqa: E731

    assert run("add", "Owner@Example.com", "--name", "Owner", "--password-stdin", stdin=PASSWORD + "\n")[0] == 0
    code, _, err = run("add", "owner@example.com", "--password-stdin", stdin=PASSWORD + "\n")
    assert code == 1 and "already" in err
    code, _, err = run("add", "other@example.com", "--password-stdin", stdin="short\n")
    assert code == 2 and "8 characters" in err
    assert run("add", "not an address", "--password-stdin", stdin=PASSWORD)[0] == 2
    assert run("list")[1].startswith("owner@example.com\tOwner\treader\tpassword")

    # The account made here signs in through the web app even though sign-up is closed.
    ctx, server = start_api(tmp_path, monkeypatch, allow_signup=False)
    try:
        client = Client(server)
        assert client.sign_up(email="new@example.com")[1]["code"] == "signup_disabled"
        assert client.sign_in("owner@example.com", PASSWORD)[0] == 200
        assert client.request("GET", "/api/editions")[0] == 200
        # A new password ends the sessions that were open.
        assert run("passwd", "owner@example.com", "--password-stdin", stdin="another long password\n")[0] == 0
        assert client.request("GET", "/api/editions")[0] == 401
        assert Client(server).sign_in("owner@example.com", "another long password")[0] == 200
        assert run("remove", "owner@example.com")[0] == 0
        assert run("remove", "owner@example.com")[0] == 1
        assert Client(server).sign_in("owner@example.com", "another long password")[0] == 401
    finally:
        server.shutdown()
        server.server_close()
