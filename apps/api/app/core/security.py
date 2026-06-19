"""Security primitives: argon2id passwords, JWT, refresh tokens, CSRF, Secret.

No secret material is ever logged or rendered. The :class:`Secret` wrapper
shows only a non-reversible fingerprint in ``repr``/``str``. JWT decoding pins
``algorithms=['HS256']`` and verifies ``exp``/``iat``/``typ`` so ``alg:none``
and algorithm-confusion attacks are rejected.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2 import exceptions as argon2_exceptions
from argon2.low_level import Type

from app.core.config import settings

# --------------------------------------------------------------------------- #
# argon2id password hashing
# --------------------------------------------------------------------------- #

# ~64 MiB / t=2 / p=2 per ARCHITECTURE.md section 10. memory_cost is in KiB.
_ARGON2_MEMORY_KIB = 64 * 1024
_ARGON2_TIME_COST = 2
_ARGON2_PARALLELISM = 2

_password_hasher = PasswordHasher(
    time_cost=_ARGON2_TIME_COST,
    memory_cost=_ARGON2_MEMORY_KIB,
    parallelism=_ARGON2_PARALLELISM,
    type=Type.ID,
)


def hash_password(password: str) -> str:
    """Return an argon2id encoded hash (params embedded in the string)."""
    return _password_hasher.hash(password)


def verify_password(encoded_hash: str, password: str) -> bool:
    """Constant-time-ish verify. Returns False on any mismatch/corruption."""
    try:
        return _password_hasher.verify(encoded_hash, password)
    except (
        argon2_exceptions.VerifyMismatchError,
        argon2_exceptions.VerificationError,
        argon2_exceptions.InvalidHashError,
    ):
        return False


def password_needs_rehash(encoded_hash: str) -> bool:
    """True if the hash was produced with weaker params than current policy."""
    try:
        return _password_hasher.check_needs_rehash(encoded_hash)
    except argon2_exceptions.InvalidHashError:
        # Unparseable hash: treat as needing a rehash on next successful login.
        return True


# --------------------------------------------------------------------------- #
# Redacting Secret wrapper
# --------------------------------------------------------------------------- #


def _fingerprint(value: str) -> str:
    """Non-reversible short fingerprint: last-4 + sha256 prefix."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    tail = value[-4:] if len(value) >= 4 else ""
    return f"***{tail}:{digest}"


@dataclass(frozen=True)
class Secret:
    """Wraps a sensitive string so it never leaks via repr/str/logging.

    Call :meth:`reveal` only at the exact point the raw value is needed
    (e.g. signing, provider call). ``repr``/``str`` emit only a fingerprint.
    """

    _value: str

    def reveal(self) -> str:
        """Return the underlying secret. Use sparingly; never log the result."""
        return self._value

    @property
    def fingerprint(self) -> str:
        """Stable non-secret fingerprint safe to log/return."""
        return _fingerprint(self._value)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"Secret({self.fingerprint})"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.fingerprint


# --------------------------------------------------------------------------- #
# JWT access tokens (HS256, pinned)
# --------------------------------------------------------------------------- #

_JWT_ALG = "HS256"
_ACCESS_TYP = "access"


class TokenError(Exception):
    """Raised when an access token is missing, invalid, expired, or tampered."""


def _jwt_secret() -> str:
    secret = settings.jwt_secret
    if not secret:
        raise TokenError("JWT secret is not configured")
    return secret


def create_access_token(
    *,
    user_id: uuid.UUID | str,
    role: str,
    token_version: int,
    expires_in_seconds: int | None = None,
) -> str:
    """Mint a short-lived access JWT with the canonical claim set.

    Claims: ``{sub, role, tv, iat, exp, jti, typ:'access'}``.
    """
    ttl = (
        expires_in_seconds
        if expires_in_seconds is not None
        else settings.access_token_ttl_minutes * 60
    )
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "tv": token_version,
        "iat": now,
        "exp": now + ttl,
        "jti": secrets.token_urlsafe(16),
        "typ": _ACCESS_TYP,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_JWT_ALG)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode + verify an access JWT. Pins HS256 and checks exp/iat/typ.

    Raises :class:`TokenError` on any failure (expired, tampered signature,
    wrong/absent algorithm, wrong ``typ``, missing required claims).
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[_JWT_ALG],
            options={
                "require": ["sub", "role", "tv", "iat", "exp", "typ"],
                "verify_exp": True,
                "verify_signature": True,
            },
        )
    except jwt.PyJWTError as exc:
        raise TokenError(f"Invalid access token: {exc}") from exc

    if payload.get("typ") != _ACCESS_TYP:
        raise TokenError("Wrong token type")
    return payload


# --------------------------------------------------------------------------- #
# Opaque refresh tokens
# --------------------------------------------------------------------------- #


def generate_refresh_token() -> str:
    """Return a fresh 256-bit URL-safe opaque refresh token (plaintext)."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Return the sha256 hex digest stored in ``refresh_tokens.token_hash``."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# CSRF double-submit tokens
# --------------------------------------------------------------------------- #


def generate_csrf_token() -> str:
    """Return a random CSRF token (set as a readable cookie + echoed header)."""
    return secrets.token_urlsafe(32)


def csrf_tokens_match(cookie_token: str | None, header_token: str | None) -> bool:
    """Constant-time double-submit comparison. False if either is missing."""
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)


__all__ = [
    "Secret",
    "TokenError",
    "hash_password",
    "verify_password",
    "password_needs_rehash",
    "create_access_token",
    "decode_access_token",
    "generate_refresh_token",
    "hash_refresh_token",
    "generate_csrf_token",
    "csrf_tokens_match",
]
