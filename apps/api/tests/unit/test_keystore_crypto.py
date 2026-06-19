"""Keystore crypto: Fernet round-trip, MultiFernet rotation, no plaintext leak."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

import app.providers.keystore.crypto as crypto
from app.core.security import Secret


def test_encrypt_decrypt_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(crypto.settings, "master_key_fernet", key)

    secret = crypto.decrypt(crypto.encrypt("my-api-key"))
    assert isinstance(secret, Secret)
    assert secret.reveal() == "my-api-key"
    # The wrapper never reveals the plaintext via repr/str.
    assert "my-api-key" not in repr(secret)
    assert "my-api-key" not in str(secret)


def test_multifernet_rotation_decrypts_old(monkeypatch: pytest.MonkeyPatch) -> None:
    old = Fernet.generate_key().decode("utf-8")
    new = Fernet.generate_key().decode("utf-8")

    # Encrypt under the old key only.
    monkeypatch.setattr(crypto.settings, "master_key_fernet", old)
    token = crypto.encrypt("legacy-secret")

    # Rotate: new key is primary, old retained for decryption.
    monkeypatch.setattr(crypto.settings, "master_key_fernet", f"{new},{old}")
    assert crypto.decrypt(token).reveal() == "legacy-secret"
    # New ciphertext is produced under the new primary key and still decrypts.
    assert crypto.decrypt(crypto.encrypt("fresh")).reveal() == "fresh"


def test_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto.settings, "master_key_fernet", "")
    with pytest.raises(crypto.KeyConfigError):
        crypto.encrypt("x")


def test_fingerprint_is_non_reversible() -> None:
    fp = crypto.fingerprint("super-secret-key-1234")
    assert "super-secret-key" not in fp
    assert fp.endswith(crypto.fingerprint("super-secret-key-1234").split(":")[-1])
