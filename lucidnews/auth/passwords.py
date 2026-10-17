"""Password hashing with scrypt (standard library): salted, memory-hard, constant-time compare."""

import base64
import hashlib
import hmac
import secrets
from functools import lru_cache
from pathlib import Path

MIN_LENGTH = 8
MAX_LENGTH = 128  # bounds the work an attacker can force per request
_N, _R, _P = 2**14, 8, 1
_DKLEN = 32


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=_DKLEN, maxmem=64 * 1024 * 1024)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _derive(password, salt, _N, _R, _P)
    b64 = lambda raw: base64.b64encode(raw).decode("ascii")  # noqa: E731
    return f"scrypt${_N}${_R}${_P}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = _derive(password, base64.b64decode(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Verified when the e-mail is unknown, so a sign-in takes the same time either way.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


@lru_cache(maxsize=1)
def _common() -> frozenset[str]:
    lines = (Path(__file__).with_name("common_passwords.txt")).read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip().lower() for line in lines if line.strip() and not line.startswith("#"))


_ROWS = ("1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm", "azertyuiop", "qsdfghjklm", "wxcvbn", "abcdefghijklmnopqrstuvwxyz")


def _guessable(password: str, email: str | None) -> bool:
    """A password an attacker tries first: a listed one, one character repeated, a keyboard run,
    or the account's own address (ASVS 2.1.7 asks for a check of this kind)."""
    lowered = password.lower()
    if lowered in _common() or len(set(lowered)) <= 2:
        return True
    if any(lowered in row or lowered in row[::-1] for row in _ROWS):
        return True
    if email:
        local = email.lower().split("@")[0]
        if lowered in (email.lower(), local) or (len(local) >= 4 and lowered.startswith(local) and lowered[len(local):].isdigit()):
            return True
    return False


def password_problem(password: object, email: str | None = None) -> str | None:
    """None when acceptable, else a short machine-readable reason."""
    if not isinstance(password, str):
        return "required"
    if len(password) < MIN_LENGTH:
        return "too_short"
    if len(password) > MAX_LENGTH:
        return "too_long"
    if _guessable(password, email):
        return "too_common"
    return None
