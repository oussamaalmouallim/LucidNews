"""Sign up, sign in, sign out and Google sign-in, as HTTP routes under ``/api/auth``.

No e-mail verification (a requirement), which has two consequences handled here:

- an address typed at sign-up is not proven to belong to the person. If that address later
  signs in with Google, which *does* verify it, the existing account becomes a Google account:
  its password is removed and its other sessions end. Otherwise whoever registered the address
  first, with a password, would keep access to the real owner's account;
- sign-up reveals whether an address is already used (the form must say so).

Accounts made here are readers; administrators are made with ``lucidnews-users``.

``/api/auth/account*`` is the signed-in person's own account (lot 28): name, password, open
sessions, export of their data and deletion. Nothing there involves e-mail.

Sessions are server-side, in an HttpOnly, SameSite=Lax cookie (``Secure`` on https).
"""

import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Deque, Dict, List, Mapping, Optional
from urllib.parse import urlsplit

from pydantic import ValidationError

from ..models import AuthConfig
from ..newsletter.provider import secret
from .google import GoogleError, GoogleOAuth
from .passwords import DUMMY_HASH, hash_password, password_problem, verify_password
from .preferences import ReaderPreferences
from .store import AuthDB, User


BASE = "/api/auth"
SESSION_COOKIE = "lucidnews_session"
FLOW_COOKIE = "lucidnews_oauth"
EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
MAX_EMAIL = 254
MAX_NAME = 80
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass
class AuthRequest:
    method: str
    path: str
    query: Dict[str, List[str]]
    body: Dict[str, Any]
    headers: Mapping[str, str]
    client_ip: str


@dataclass
class AuthResult:
    status: int
    body: Optional[Dict[str, Any]] = None
    cookies: List[str] = field(default_factory=list)
    location: Optional[str] = None


class RateLimiter:
    """At most ``limit`` events per key in ``window`` seconds (memory only: a restart forgets)."""

    def __init__(self, limit: int, window: float, clock=time.monotonic):
        self.limit, self.window, self._clock = limit, window, clock
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        """Record an event; False when the key is over the limit."""
        now = self._clock()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - self.window:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            if len(self._events) > 10_000:  # bound memory under a flood of distinct keys
                self._events = defaultdict(deque, {k: v for k, v in self._events.items() if v})
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


def _error(status: int, code: str, message: str, **extra: Any) -> AuthResult:
    return AuthResult(status, {"error": message, "code": code, **extra})


def safe_next(value: Optional[str]) -> str:
    """Only a path of this site: never ``//host``, a scheme or a backslash (open redirect)."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value or any(ord(c) < 32 for c in value):
        return "/"
    return value if not value.startswith(BASE) and not value.startswith("/sign-") else "/"


ACCOUNT = f"{BASE}/account"

BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"))
SYSTEMS = (("iPhone", "iOS"), ("iPad", "iPadOS"), ("Android", "Android"), ("Mac OS X", "macOS"), ("Windows", "Windows"), ("Linux", "Linux"))


def device_label(user_agent: Optional[str]) -> Optional[str]:
    """"Firefox · macOS" from a User-Agent; None when nothing is recognized (never the raw string)."""
    if not user_agent:
        return None
    browser = next((name for marker, name in BROWSERS if marker in user_agent), None)
    system = next((name for marker, name in SYSTEMS if marker in user_agent), None)
    return " · ".join(part for part in (browser, system) if part) or None


class AuthService:
    def __init__(self, config: AuthConfig, db: AuthDB, *, google: Optional[GoogleOAuth] = None):
        self.config = config
        self.db = db
        self.google = google
        self.signin_by_ip = RateLimiter(20, 900)
        self.signin_by_email = RateLimiter(8, 900)
        self.signup_by_ip = RateLimiter(10, 3600)
        self.password_checks = RateLimiter(8, 900)  # per account: current-password checks
        self._secure = bool(config.public_url and config.public_url.startswith("https://"))

    # Session ----------------------------------------------------------------------------------

    @staticmethod
    def _cookie(headers: Mapping[str, str], name: str) -> Optional[str]:
        raw = headers.get("Cookie")
        if not raw:
            return None
        jar: SimpleCookie = SimpleCookie()
        try:
            jar.load(raw)
        except Exception:
            return None
        morsel = jar.get(name)
        return morsel.value if morsel else None

    def current_user(self, headers: Mapping[str, str]) -> Optional[User]:
        token = self._cookie(headers, SESSION_COOKIE)
        return self.db.session_user(token, self.config.session_days) if token else None

    def _set_cookie(self, name: str, value: str, max_age: int, path: str = "/") -> str:
        parts = [f"{name}={value}", f"Path={path}", f"Max-Age={max_age}", "HttpOnly", "SameSite=Lax"]
        if self._secure:
            parts.append("Secure")
        return "; ".join(parts)

    def _session_cookie(self, user: User, headers: Optional[Mapping[str, str]] = None) -> str:
        token = self.db.create_session(user.id, self.config.session_days, device_label((headers or {}).get("User-Agent")))
        return self._set_cookie(SESSION_COOKIE, token, self.config.session_days * 86400)

    def _state(self, user: Optional[User]) -> Dict[str, Any]:
        return {
            "enabled": True,
            "authenticated": user is not None,
            "user": user.public() if user else None,
            "signup_enabled": self.config.allow_signup,
            "providers": {"google": self.google is not None},
        }

    # Routes -----------------------------------------------------------------------------------

    def handle(self, request: AuthRequest) -> AuthResult:
        route = (request.method, request.path.rstrip("/"))
        if route == ("GET", f"{BASE}/session"):
            return AuthResult(HTTPStatus.OK, self._state(self.current_user(request.headers)))
        if route == ("GET", f"{BASE}/google/start"):
            return self._google_start(request)
        if route == ("GET", f"{BASE}/google/callback"):
            return self._google_callback(request)
        if request.path.rstrip("/").startswith(ACCOUNT):
            return self._account(request)
        if request.method == "POST" and request.path.rstrip("/") in (f"{BASE}/sign-up", f"{BASE}/sign-in", f"{BASE}/sign-out"):
            if not self.same_origin(request.headers):
                return _error(HTTPStatus.FORBIDDEN, "forbidden", "cross-site request refused")
            action = request.path.rstrip("/").rsplit("/", 1)[1]
            return {"sign-up": self._sign_up, "sign-in": self._sign_in, "sign-out": self._sign_out}[action](request)
        return _error(HTTPStatus.NOT_FOUND, "not_found", "not found")

    def same_origin(self, headers: Mapping[str, str]) -> bool:
        """A browser always sends Origin on a POST: it must be this site (or the configured public URL)."""
        origin = headers.get("Origin")
        if origin is None:
            return True  # not a browser: nothing to forge
        allowed = {(headers.get("Host") or "").lower()}
        if self.config.public_url:
            allowed.add(urlsplit(self.config.public_url).netloc.lower())
        return urlsplit(origin).netloc.lower() in allowed

    def _sign_up(self, request: AuthRequest) -> AuthResult:
        if not self.config.allow_signup:
            return _error(HTTPStatus.FORBIDDEN, "signup_disabled", "sign-up is closed")
        if not self.signup_by_ip.hit(request.client_ip):
            return _error(HTTPStatus.TOO_MANY_REQUESTS, "rate_limited", "too many attempts, try again later")
        email = self._email(request.body.get("email"))
        if email is None:
            return _error(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_email", "enter a valid e-mail address")
        problem = password_problem(request.body.get("password"))
        if problem:
            return _error(HTTPStatus.UNPROCESSABLE_ENTITY, "weak_password", "password does not meet the rules", reason=problem)
        name = self._name(request.body.get("name")) or email.split("@")[0]
        user = self.db.create_user(email, name, password_hash=hash_password(request.body["password"]))
        if user is None:
            return _error(HTTPStatus.CONFLICT, "email_taken", "an account already uses this e-mail address")
        return AuthResult(HTTPStatus.CREATED, self._state(user), [self._session_cookie(user, request.headers)])

    def _sign_in(self, request: AuthRequest) -> AuthResult:
        email = self._email(request.body.get("email"))
        password = request.body.get("password")
        if not self.signin_by_ip.hit(request.client_ip) or (email and not self.signin_by_email.hit(email)):
            return _error(HTTPStatus.TOO_MANY_REQUESTS, "rate_limited", "too many attempts, try again later")
        found = self.db.by_email(email) if email else None
        stored = found[1] if found else None
        # Same work whether or not the account exists, so timing does not reveal it.
        matches = verify_password(password if isinstance(password, str) else "", stored or DUMMY_HASH)
        if found is not None and stored is None:
            return _error(HTTPStatus.UNAUTHORIZED, "use_google", "this account signs in with Google")
        if found is None or not matches:
            return _error(HTTPStatus.UNAUTHORIZED, "invalid_credentials", "incorrect e-mail or password")
        user = found[0]
        self.signin_by_email.reset(email)
        self.db.touch_login(user.id)
        return AuthResult(HTTPStatus.OK, self._state(user), [self._session_cookie(user, request.headers)])

    def _sign_out(self, request: AuthRequest) -> AuthResult:
        token = self._cookie(request.headers, SESSION_COOKIE)
        if token:
            self.db.delete_session(token)
        return AuthResult(HTTPStatus.OK, self._state(None), [self._set_cookie(SESSION_COOKIE, "", 0)])

    # Account (the signed-in person's own) ---------------------------------------------------

    def _account(self, request: AuthRequest) -> AuthResult:
        token = self._cookie(request.headers, SESSION_COOKIE)
        user = self.db.session_user(token, self.config.session_days) if token else None
        if user is None or token is None:
            return _error(HTTPStatus.UNAUTHORIZED, "unauthenticated", "authentication required")
        if request.method != "GET" and not self.same_origin(request.headers):
            return _error(HTTPStatus.FORBIDDEN, "forbidden", "cross-site request refused")
        route = (request.method, request.path.rstrip("/").removeprefix(ACCOUNT))
        if route == ("GET", ""):
            return AuthResult(HTTPStatus.OK, self._account_state(user, token))
        if route == ("PUT", ""):
            name = self._name(request.body.get("name"))
            if not name:
                return _error(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_name", "enter a name")
            self.db.rename(user.id, name)
            return AuthResult(HTTPStatus.OK, self._account_state(self.db.get(user.id) or user, token))
        if route == ("POST", "/password"):
            return self._change_password(request, user, token)
        if route == ("POST", "/sessions/close-others"):
            closed = self.db.delete_other_sessions(user.id, token)
            return AuthResult(HTTPStatus.OK, {**self._account_state(user, token), "closed": closed})
        if request.method == "DELETE" and route[1].startswith("/sessions/"):
            session_id = route[1].removeprefix("/sessions/")
            if session_id == self.db.session_id(token):
                return _error(HTTPStatus.CONFLICT, "current_session", "sign out to end this session")
            if not self.db.delete_session_by_id(user.id, session_id):
                return _error(HTTPStatus.NOT_FOUND, "not_found", "no such session")
            return AuthResult(HTTPStatus.OK, self._account_state(user, token))
        if route == ("GET", "/preferences"):
            return AuthResult(HTTPStatus.OK, self._preferences_state(user))
        if route == ("PUT", "/preferences"):
            try:
                preferences = ReaderPreferences.model_validate(request.body)
            except ValidationError as exc:
                fields = {".".join(str(p) for p in err["loc"]) or "body": err["msg"] for err in exc.errors()}
                return _error(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_preferences", "invalid preferences", fields=fields)
            self.db.save_preferences(user.id, preferences.model_dump_json())
            return AuthResult(HTTPStatus.OK, self._preferences_state(user))
        if route == ("GET", "/export"):
            return AuthResult(HTTPStatus.OK, self._export(user, token))
        if route == ("POST", "/delete"):
            return self._delete(request, user)
        return _error(HTTPStatus.NOT_FOUND, "not_found", "not found")

    def _account_state(self, user: User, token: str) -> Dict[str, Any]:
        current = self.db.session_id(token)
        return {
            "user": user.public(),
            "sessions": [{**session, "current": session["id"] == current} for session in self.db.list_sessions(user.id)],
            # The last administrator cannot leave: the newsroom would have nobody to run it.
            "can_delete": not (user.is_admin and self.db.count_admins() <= 1),
            "session_days": self.config.session_days,
        }

    def _check_current_password(self, user: User, given: object) -> Optional[AuthResult]:
        """None when the account has no password (Google) or the one given is right."""
        stored = self.db.password_hash(user.id)
        if stored is None:
            return None
        if not self.password_checks.hit(user.id):
            return _error(HTTPStatus.TOO_MANY_REQUESTS, "rate_limited", "too many attempts, try again later")
        if not verify_password(given if isinstance(given, str) else "", stored):
            return _error(HTTPStatus.UNAUTHORIZED, "wrong_password", "the current password is incorrect")
        self.password_checks.reset(user.id)
        return None

    def _change_password(self, request: AuthRequest, user: User, token: str) -> AuthResult:
        refused = self._check_current_password(user, request.body.get("current"))
        if refused:
            return refused
        problem = password_problem(request.body.get("password"))
        if problem:
            return _error(HTTPStatus.UNPROCESSABLE_ENTITY, "weak_password", "password does not meet the rules", reason=problem)
        self.db.change_password(user.id, hash_password(request.body["password"]), token)
        return AuthResult(HTTPStatus.OK, self._account_state(self.db.get(user.id) or user, token))

    def preferences_of(self, user: User) -> tuple[ReaderPreferences, Optional[str]]:
        """The reader's saved preferences (defaults before the first save) and when they were saved.
        A stored value that no longer validates (a domain removed since) falls back to the defaults."""
        stored = self.db.preferences(user.id)
        if stored is None:
            return ReaderPreferences(), None
        try:
            return ReaderPreferences.model_validate_json(stored[0]), stored[1]
        except ValidationError:
            return ReaderPreferences(), stored[1]

    def _preferences_state(self, user: User) -> Dict[str, Any]:
        preferences, updated_at = self.preferences_of(user)
        return {"preferences": preferences.model_dump(mode="json"), "filters": preferences.filters, "updated_at": updated_at}

    def _export(self, user: User, token: str) -> Dict[str, Any]:
        """Everything kept about the person (loi 09-08, RGPD): never a hash, a token or the Google id."""
        dates = self.db.account_row(user.id) or {}
        public = user.public()
        return {
            "format": "lucidnews-account-export/1",
            "account": {
                "email": public["email"],
                "name": public["name"],
                "role": public["role"],
                "picture": public["picture"],
                "sign_in_methods": [m for m, on in (("password", user.has_password), ("google", user.google_sub is not None)) if on],
                "created_at": dates.get("created_at"),
                "last_login_at": dates.get("last_login_at"),
            },
            "sessions": [
                {key: session[key] for key in ("created_at", "last_seen_at", "expires_at", "device")}
                for session in self.db.list_sessions(user.id)
            ],
            "preferences": self._preferences_state(user),
        }

    def _delete(self, request: AuthRequest, user: User) -> AuthResult:
        if user.is_admin and self.db.count_admins() <= 1:
            return _error(HTTPStatus.CONFLICT, "last_admin", "the last administrator cannot delete their account")
        if self.db.password_hash(user.id) is None:
            # No password to ask for (Google): typing the address confirms it.
            if self._email(request.body.get("email")) != user.email.lower():
                return _error(HTTPStatus.UNPROCESSABLE_ENTITY, "confirm_email", "type your e-mail address to confirm")
        else:
            refused = self._check_current_password(user, request.body.get("current"))
            if refused:
                return refused
        self.db.delete_user(user.id)
        return AuthResult(HTTPStatus.OK, self._state(None), [self._set_cookie(SESSION_COOKIE, "", 0)])

    # Google -----------------------------------------------------------------------------------

    def _base_url(self, headers: Mapping[str, str]) -> Optional[str]:
        """Where the browser reaches this app. A Host header is trusted only for localhost."""
        if self.config.public_url:
            return self.config.public_url
        host = headers.get("Host") or ""
        hostname = host.rsplit(":", 1)[0].strip("[]") if not host.startswith("[") else host.split("]")[0].strip("[")
        return f"http://{host}" if hostname in LOCAL_HOSTS else None

    def _google_start(self, request: AuthRequest) -> AuthResult:
        base = self._base_url(request.headers)
        if self.google is None or base is None:
            return self._to_sign_in("google_unavailable")
        try:
            url, binder = self.google.begin(f"{base}{BASE}/google/callback", safe_next((request.query.get("next") or [""])[0]))
        except GoogleError as exc:
            return self._to_sign_in(exc.code)
        return AuthResult(HTTPStatus.FOUND, cookies=[self._set_cookie(FLOW_COOKIE, binder, 600, path=BASE)], location=url)

    def _google_callback(self, request: AuthRequest) -> AuthResult:
        base = self._base_url(request.headers)
        clear = self._set_cookie(FLOW_COOKIE, "", 0, path=BASE)
        code, state = (request.query.get("code") or [""])[0], (request.query.get("state") or [""])[0]
        if self.google is None or base is None:
            return self._to_sign_in("google_unavailable", [clear])
        if (request.query.get("error") or [""])[0]:
            self.google.cancel(state)  # the reader declined at Google
            return self._to_sign_in("google_cancelled", [clear])
        if not code or not state:
            return self._to_sign_in("state_invalid", [clear])
        try:
            profile, next_path = self.google.complete(code, state, self._cookie(request.headers, FLOW_COOKIE), f"{base}{BASE}/google/callback")
        except GoogleError as exc:
            return self._to_sign_in(exc.code, [clear])
        user = self.db.by_google_sub(profile.sub)
        if user is None:
            existing = self.db.by_email(profile.email)
            if existing is not None:
                user = existing[0]
                if user.google_sub is not None:
                    return self._to_sign_in("account_conflict", [clear])
                # An address registered with a password was never verified: Google proves it, so the
                # password (possibly set by someone else) goes and every session of the account ends.
                self.db.link_google(user.id, profile.sub, profile.picture)
                self.db.delete_user_sessions(user.id)
            elif not self.config.allow_signup:
                return self._to_sign_in("signup_disabled", [clear])
            else:
                user = self.db.create_user(profile.email, self._name(profile.name) or profile.email.split("@")[0], google_sub=profile.sub, picture=profile.picture)
                if user is None:
                    return self._to_sign_in("account_conflict", [clear])
        self.db.touch_login(user.id)
        return AuthResult(HTTPStatus.FOUND, cookies=[clear, self._session_cookie(user, request.headers)], location=next_path)

    @staticmethod
    def _to_sign_in(code: str, cookies: Optional[List[str]] = None) -> AuthResult:
        return AuthResult(HTTPStatus.FOUND, cookies=cookies or [], location=f"/sign-in?error={code}")

    # Input ------------------------------------------------------------------------------------

    @staticmethod
    def _email(value: object) -> Optional[str]:
        if not isinstance(value, str):
            return None
        email = value.strip().lower()
        return email if len(email) <= MAX_EMAIL and EMAIL_PATTERN.match(email) else None

    @staticmethod
    def _name(value: object) -> str:
        if not isinstance(value, str):
            return ""
        return re.sub(r"[\x00-\x1f\x7f]", "", value).strip()[:MAX_NAME]


def build_auth_service(config: AuthConfig, data_dir: Path) -> Optional[AuthService]:
    """None when authentication is off. Google is offered only when its credentials are set."""
    if not config.enabled:
        return None
    client_id, client_secret = secret(config.google_client_id_env), secret(config.google_client_secret_env)
    google = GoogleOAuth(client_id, client_secret) if client_id and client_secret else None
    return AuthService(config, AuthDB(Path(data_dir) / "auth.sqlite3"), google=google)
