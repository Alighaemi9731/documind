"""crypto.rotate_ciphertext: re-encrypt under the new key while old still decrypts;
fingerprint embeds no raw key material."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

import app.providers.keystore.crypto as crypto


def test_rotate_ciphertext_reencrypts_under_new_key(monkeypatch: pytest.MonkeyPatch) -> None:
    old = Fernet.generate_key().decode("utf-8")
    new = Fernet.generate_key().decode("utf-8")

    # Encrypt under the OLD key only.
    monkeypatch.setattr(crypto.settings, "master_key_fernet", old)
    old_ct = crypto.encrypt("byok-secret")

    # Rotate config: NEW key primary, old retained for decryption.
    monkeypatch.setattr(crypto.settings, "master_key_fernet", f"{new},{old}")
    rotated = crypto.rotate_ciphertext(old_ct)
    # The rotated ciphertext is a different token but the same plaintext.
    assert rotated != old_ct
    assert crypto.decrypt(rotated).reveal() == "byok-secret"

    # After retiring the OLD key, the rotated ciphertext STILL decrypts under new.
    monkeypatch.setattr(crypto.settings, "master_key_fernet", new)
    assert crypto.decrypt(rotated).reveal() == "byok-secret"
    # And the pre-rotation token would no longer decrypt (old key retired).
    with pytest.raises(Exception):  # noqa: B017,PT011 - InvalidToken under new key only
        crypto.decrypt(old_ct)


def test_fingerprint_has_no_raw_material() -> None:
    raw = "sk-supersecret-abcdef-1234567890"
    fp = crypto.fingerprint(raw)
    assert fp.startswith("sha256:")
    assert raw not in fp
    # Not even the last few characters of the key appear in the fingerprint.
    assert raw[-4:] not in fp
