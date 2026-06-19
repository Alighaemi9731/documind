"""Quota service integration: atomic reserve, shared-only enforcement, BYOK
bypass, global ceiling, hard-disable, and key_source attribution (ADR-0009).

Runs against the real RLS-FORCEd Postgres (user_monthly_usage is owner-only)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core.db import admin_session, tenant_session
from app.models.enums import Capability, KeySource
from app.models.usage import UserQuota
from app.models.user import User
from app.services import quota_service

pytestmark = pytest.mark.asyncio


async def _make_user() -> uuid.UUID:
    uid = uuid.uuid4()
    async with admin_session() as session:
        session.add(User(id=uid, email=f"{uid}@example.com"))
        await session.flush()
    return uid


async def _set_limit(uid: uuid.UUID, limit: int | None, *, hard_disabled: bool = False) -> None:
    async with tenant_session(uid) as session:
        session.add(UserQuota(user_id=uid, monthly_token_limit=limit, hard_disabled=hard_disabled))
        await session.flush()


async def test_shared_reserve_and_reconcile(app_db: None) -> None:
    uid = await _make_user()
    await _set_limit(uid, 1_000_000)
    async with tenant_session(uid) as session:
        res = await quota_service.check_and_reserve(
            session, user_id=uid, key_source=KeySource.shared, estimate=1000
        )
        assert res.key_source is KeySource.shared
        assert res.reserved == 1000
        # Reconcile against actual 1500 tokens.
        await quota_service.record_usage(
            session,
            reservation=res,
            provider="google",
            capability=Capability.chat,
            project_id=None,
            tokens_in=1000,
            tokens_out=500,
        )
        row = (
            await session.execute(
                text("SELECT tokens FROM user_monthly_usage WHERE user_id = :u"),
                {"u": str(uid)},
            )
        ).scalar()
        assert int(row) == 1500  # reserved 1000 + (1500 actual - 1000 reserved)


async def test_byok_bypasses_quota(app_db: None) -> None:
    uid = await _make_user()
    await _set_limit(uid, 1)  # tiny limit; BYOK must ignore it
    async with tenant_session(uid) as session:
        res = await quota_service.check_and_reserve(
            session, user_id=uid, key_source=KeySource.byok, estimate=10_000
        )
        assert res.key_source is KeySource.byok
        assert res.reserved == 0
        await quota_service.record_usage(
            session,
            reservation=res,
            provider="openai",
            capability=Capability.chat,
            project_id=None,
            tokens_in=10_000,
            tokens_out=5_000,
        )
        # No counter row was created/incremented for BYOK.
        row = (
            await session.execute(
                text("SELECT COALESCE(SUM(tokens),0) FROM user_monthly_usage WHERE user_id = :u"),
                {"u": str(uid)},
            )
        ).scalar()
        assert int(row) == 0


async def test_shared_over_limit_rejected_429(app_db: None) -> None:
    uid = await _make_user()
    await _set_limit(uid, 1000)
    async with tenant_session(uid) as session:
        await quota_service.check_and_reserve(
            session, user_id=uid, key_source=KeySource.shared, estimate=900
        )
        # Second reserve crosses the 1000 limit -> rejected, and rolled back.
        with pytest.raises(quota_service.QuotaExceeded):
            await quota_service.check_and_reserve(
                session, user_id=uid, key_source=KeySource.shared, estimate=900
            )
        row = (
            await session.execute(
                text("SELECT tokens FROM user_monthly_usage WHERE user_id = :u"),
                {"u": str(uid)},
            )
        ).scalar()
        # The failed reservation was undone; only the first 900 stands.
        assert int(row) == 900


async def test_global_ceiling_rejected(app_db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    uid = await _make_user()
    await _set_limit(uid, 1_000_000)  # generous per-user; global is the backstop
    monkeypatch.setattr(quota_service.settings, "global_monthly_token_ceiling", 500)
    async with tenant_session(uid) as session:
        with pytest.raises(quota_service.QuotaExceeded):
            await quota_service.check_and_reserve(
                session, user_id=uid, key_source=KeySource.shared, estimate=600
            )


async def test_global_ceiling_is_install_wide_across_users(
    app_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The global ceiling is INSTALL-wide: one user is rejected because OTHER
    users have already consumed the shared key, even though it is under its own
    per-user limit."""
    a = await _make_user()
    b = await _make_user()
    await _set_limit(a, 1_000_000)
    await _set_limit(b, 1_000_000)  # generous per-user; the GLOBAL ceiling is the cap
    monkeypatch.setattr(quota_service.settings, "global_monthly_token_ceiling", 1000)

    async with tenant_session(a) as session:
        await quota_service.check_and_reserve(
            session, user_id=a, key_source=KeySource.shared, estimate=700
        )

    async with tenant_session(b) as session:
        # 700 (A) + 700 (B) = 1400 > 1000 install ceiling -> B is rejected.
        with pytest.raises(quota_service.QuotaExceeded):
            await quota_service.check_and_reserve(
                session, user_id=b, key_source=KeySource.shared, estimate=700
            )
        # B's own counter was rolled back (no partial charge).
        row = (
            await session.execute(
                text("SELECT COALESCE(tokens, 0) FROM user_monthly_usage WHERE user_id = :u"),
                {"u": str(b)},
            )
        ).scalar()
        assert int(row or 0) == 0


async def test_hard_disabled_rejected(app_db: None) -> None:
    uid = await _make_user()
    await _set_limit(uid, 1_000_000, hard_disabled=True)
    async with tenant_session(uid) as session:
        with pytest.raises(quota_service.QuotaDisabled):
            await quota_service.check_and_reserve(
                session, user_id=uid, key_source=KeySource.shared, estimate=10
            )


async def test_key_source_attribution_recorded(app_db: None) -> None:
    """A shared reservation can never be recorded as byok and vice-versa."""
    uid = await _make_user()
    await _set_limit(uid, 1_000_000)
    async with tenant_session(uid) as session:
        shared = await quota_service.check_and_reserve(
            session, user_id=uid, key_source=KeySource.shared, estimate=10
        )
        await quota_service.record_usage(
            session,
            reservation=shared,
            provider="google",
            capability=Capability.embedding,
            project_id=None,
            tokens_in=10,
            tokens_out=0,
        )
        rows = (
            await session.execute(
                text("SELECT key_source FROM usage_events WHERE user_id = :u"),
                {"u": str(uid)},
            )
        ).all()
        assert [r[0] for r in rows] == ["shared"]
