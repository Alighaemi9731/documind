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


async def test_admin_email_claims_passwordless_bootstrap_account(app_db: None) -> None:
    """The configured admin email can self-register to CLAIM its passwordless
    bootstrap account: the password is set and it stays an active admin, and a
    later registration of the same email is a genuine duplicate."""
    from app.models.enums import RegistrationMode
    from app.services import auth_service

    await _bootstrap_admin("owner@example.com")  # passwordless admin

    async with admin_session() as session:
        claimed = await auth_service.register(
            session,
            email="owner@example.com",
            password="correct-horse-battery-staple",
            registration_mode=RegistrationMode.open,
            invite_token=None,
            admin_email="owner@example.com",
        )
        assert claimed.role is UserRole.admin
        assert claimed.status is UserStatus.active

        # The password now authenticates.
        authed = await auth_service.authenticate(
            session, email="owner@example.com", password="correct-horse-battery-staple"
        )
        assert authed.id == claimed.id

        # Claiming is one-shot: a second registration is now a duplicate.
        with pytest.raises(auth_service.AuthError) as exc:
            await auth_service.register(
                session,
                email="owner@example.com",
                password="another-pass-phrase",
                registration_mode=RegistrationMode.open,
                invite_token=None,
                admin_email="owner@example.com",
            )
        assert exc.value.code == "email_taken"


async def test_non_admin_existing_email_is_not_claimable(app_db: None) -> None:
    """Only the CONFIGURED admin email may claim an existing account. Any other
    existing email is rejected (no account takeover via re-registration)."""
    from app.models.enums import RegistrationMode
    from app.models.user import User
    from app.services import auth_service

    async with admin_session() as session:
        session.add(User(email="someone@example.com", role=UserRole.user, status=UserStatus.active))
        await session.flush()

    async with admin_session() as session:
        with pytest.raises(auth_service.AuthError) as exc:
            await auth_service.register(
                session,
                email="someone@example.com",
                password="correct-horse-battery-staple",
                registration_mode=RegistrationMode.open,
                invite_token=None,
                admin_email="owner@example.com",  # different from someone@
            )
        assert exc.value.code == "email_taken"
