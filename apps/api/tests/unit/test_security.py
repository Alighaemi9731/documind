"""Unit tests for core/security.py (no database required)."""

from __future__ import annotations

import time
import uuid

import jwt
import pytest

from app.core import security
from app.core.config import settings

# --------------------------------------------------------------------------- #
# argon2id
# --------------------------------------------------------------------------- #


def test_password_round_trip() -> None:
    encoded = security.hash_password("correct horse battery staple")
    assert encoded.startswith("$argon2id$")
    assert security.verify_password(encoded, "correct horse battery staple")
    assert not security.verify_password(encoded, "wrong password")


def test_password_needs_rehash_for_weak_params() -> None:
    # A hash produced with deliberately weaker params must be flagged.
    from argon2 import PasswordHasher
    from argon2.low_level import Type

    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1, type=Type.ID)
    weak_hash = weak.hash("pw")
    assert security.password_needs_rehash(weak_hash) is True

    strong_hash = security.hash_password("pw")
    assert security.password_needs_rehash(strong_hash) is False


def test_verify_password_handles_garbage_hash() -> None:
    assert security.verify_password("not-a-hash", "pw") is False
    assert security.password_needs_rehash("not-a-hash") is True


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #


def test_jwt_issue_and_verify() -> None:
    uid = uuid.uuid4()
    token = security.create_access_token(user_id=uid, role="user", token_version=0)
    payload = security.decode_access_token(token)
    assert payload["sub"] == str(uid)
    assert payload["role"] == "user"
    assert payload["tv"] == 0
    assert payload["typ"] == "access"
    assert "jti" in payload


def test_jwt_expired_is_rejected() -> None:
    token = security.create_access_token(
        user_id=uuid.uuid4(), role="user", token_version=0, expires_in_seconds=-1
    )
    with pytest.raises(security.TokenError):
        security.decode_access_token(token)


def test_jwt_tampered_signature_is_rejected() -> None:
    token = security.create_access_token(user_id=uuid.uuid4(), role="user", token_version=0)
    # Flip a character in the signature segment.
    head, body, sig = token.split(".")
    tampered = f"{head}.{body}.{sig[:-2] + ('aa' if sig[-2:] != 'aa' else 'bb')}"
    with pytest.raises(security.TokenError):
        security.decode_access_token(tampered)


def test_jwt_alg_none_is_rejected() -> None:
    # Forge an unsigned token with alg=none; the verifier must refuse it.
    forged = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": "admin",
            "tv": 0,
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "typ": "access",
        },
        key="",
        algorithm="none",
    )
    with pytest.raises(security.TokenError):
        security.decode_access_token(forged)


def test_jwt_wrong_algorithm_is_rejected() -> None:
    # A token signed with a different (still-symmetric) alg must be rejected
    # because the verifier pins HS256.
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "user",
        "tv": 0,
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
        "typ": "access",
    }
    hs512 = jwt.encode(payload, settings.jwt_secret, algorithm="HS512")
    with pytest.raises(security.TokenError):
        security.decode_access_token(hs512)


def test_jwt_wrong_typ_is_rejected() -> None:
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "user",
        "tv": 0,
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
        "typ": "refresh",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(security.TokenError):
        security.decode_access_token(token)


def test_jwt_token_version_is_carried_for_caller_check() -> None:
    # The decoder returns tv; the tv-mismatch *rejection* is enforced by the
    # dependency against the DB. Here we assert the claim round-trips.
    token = security.create_access_token(user_id=uuid.uuid4(), role="user", token_version=7)
    assert security.decode_access_token(token)["tv"] == 7


# --------------------------------------------------------------------------- #
# Refresh tokens / CSRF / Secret
# --------------------------------------------------------------------------- #


def test_refresh_token_hash_is_stable_and_opaque() -> None:
    raw = security.generate_refresh_token()
    assert len(raw) >= 32
    h1 = security.hash_refresh_token(raw)
    h2 = security.hash_refresh_token(raw)
    assert h1 == h2
    assert len(h1) == 64
    assert raw not in h1


def test_csrf_double_submit_match() -> None:
    tok = security.generate_csrf_token()
    assert security.csrf_tokens_match(tok, tok) is True
    assert security.csrf_tokens_match(tok, "other") is False
    assert security.csrf_tokens_match(None, tok) is False
    assert security.csrf_tokens_match(tok, None) is False


def test_secret_redacts_value() -> None:
    secret = security.Secret("super-secret-key-material")
    text = f"{secret!r} {secret!s}"
    assert "super-secret-key-material" not in text
    assert secret.reveal() == "super-secret-key-material"
    assert secret.fingerprint.startswith("***")
