"""bootstrap-admin idempotency + reconciliation integration test."""

from __future__ import annotations

import pytest

from app.cli import _bootstrap_admin
from app.core.db import admin_session
from app.models.enums import UserRole, UserStatus
from app.services.auth_service import get_user_by_email

pytestmark = pytest.mark.asyncio


async def test_bootstrap_admin_is_idempotent(app_db: None) -> None:
    first = await _bootstrap_admin("admin@example.com")
    assert first == "created"

    second = await _bootstrap_admin("admin@example.com")
    assert second == "unchanged"

    async with admin_session() as session:
        user = await get_user_by_email(session, "admin@example.com")
    assert user is not None
    assert user.role is UserRole.admin
    assert user.status is UserStatus.active


async def test_bootstrap_admin_reconciles_existing_user(app_db: None) -> None:
    from app.models.user import User

    async with admin_session() as session:
        session.add(
            User(
                email="reconcile@example.com",
                role=UserRole.user,
                status=UserStatus.pending,
            )
        )
        await session.flush()

    result = await _bootstrap_admin("reconcile@example.com")
    assert result == "reconciled"

    async with admin_session() as session:
        user = await get_user_by_email(session, "reconcile@example.com")
    assert user is not None
    assert user.role is UserRole.admin
    assert user.status is UserStatus.active
