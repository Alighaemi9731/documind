"""Operator-default key: seed + load round-trip through the DB (ADR-0007)."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

import app.providers.keystore.crypto as crypto
from app.core.db import admin_session
from app.models.enums import Provider
from app.providers.keystore.operator_default import (
    OperatorKeyNotConfigured,
    load_operator_key,
    seed_operator_default,
)

pytestmark = pytest.mark.asyncio


async def test_seed_then_load(app_db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(crypto.settings, "master_key_fernet", key)

    async with admin_session() as session:
        row = await seed_operator_default(
            session, "operator-gemini-key", provider=Provider.google.value
        )
        assert row.key_version == 1
        assert "operator-gemini-key" not in row.key_fingerprint

    async with admin_session() as session:
        secret = await load_operator_key(session, provider=Provider.google.value)
    assert secret.reveal() == "operator-gemini-key"


async def test_reseed_rotates_version(app_db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(crypto.settings, "master_key_fernet", key)

    async with admin_session() as session:
        await seed_operator_default(session, "k1", provider=Provider.google.value)
    async with admin_session() as session:
        row = await seed_operator_default(session, "k2", provider=Provider.google.value)
        assert row.key_version == 2
    async with admin_session() as session:
        assert (await load_operator_key(session, provider=Provider.google.value)).reveal() == "k2"


async def test_load_missing_raises(app_db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto.settings, "master_key_fernet", Fernet.generate_key().decode())
    async with admin_session() as session:
        with pytest.raises(OperatorKeyNotConfigured):
            await load_operator_key(session, provider=Provider.google.value)
