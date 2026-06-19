"""Admin endpoints (ARCHITECTURE.md section 6/10). ``require_admin`` on every route.

Backend only — the full dashboard UI is Phase 5. Cross-user reads/writes use a
DEDICATED admin metadata session (:func:`admin_session`) over the allow-listed
metadata tables (users, invites, provider_keys metadata, usage, quota,
operator_default). This path NEVER touches document/chunk/message CONTENT — the
RLS admin bypass is granted only on metadata tables (ADR-0002). Last-admin guards
protect demote/disable/delete. Provider keys surface as fingerprints only — never
secrets.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, select

from app.api.deps import AdminUser
from app.api.errors import api_error
from app.api.schemas import (
    AdminUserList,
    AdminUserPublic,
    InviteCreateRequest,
    InviteCreateResponse,
    InvitePublic,
    KeyMetadataPublic,
    OperatorKeyPublic,
    OperatorKeyRotateRequest,
    QuotaPublic,
    QuotaUpdate,
    UsagePoint,
    UsageResponse,
)
from app.core.db import admin_session
from app.core.security import generate_refresh_token, hash_refresh_token
from app.models.enums import Provider, UserRole, UserStatus
from app.models.invite import Invite
from app.models.operator_default import OperatorDefault
from app.models.provider_key import ProviderKey
from app.models.usage import UsageEvent, UserQuota
from app.models.user import User
from app.providers.keystore import crypto
from app.providers.keystore.operator_default import seed_operator_default

router = APIRouter()

INVITE_TTL_DAYS = 14
_PAGE_SIZE = 50


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_date(value: str | None) -> datetime | None:
    """Parse an ISO date/datetime query param into a UTC-aware datetime, or None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


async def _count_active_admins(session) -> int:  # noqa: ANN001
    result = await session.execute(
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.admin, User.status == UserStatus.active)
    )
    return int(result.scalar() or 0)


async def _load_user(session, user_id: uuid.UUID) -> User:  # noqa: ANN001
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise api_error(404, "not_found", "User not found.")
    return user


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #


@router.get("/users", response_model=AdminUserList)
async def list_users(
    _admin: AdminUser,
    q: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    role: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> AdminUserList:
    """List/search users (metadata only) with status/role filters + paging."""
    async with admin_session() as session:
        stmt = select(User)
        count_stmt = select(func.count()).select_from(User)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(User.email.ilike(like))
            count_stmt = count_stmt.where(User.email.ilike(like))
        if status_filter:
            stmt = stmt.where(User.status == status_filter)
            count_stmt = count_stmt.where(User.status == status_filter)
        if role:
            stmt = stmt.where(User.role == role)
            count_stmt = count_stmt.where(User.role == role)

        total = int((await session.execute(count_stmt)).scalar() or 0)
        stmt = (
            stmt.order_by(User.created_at.desc()).offset((page - 1) * _PAGE_SIZE).limit(_PAGE_SIZE)
        )
        users = (await session.execute(stmt)).scalars().all()
        return AdminUserList(
            users=[AdminUserPublic.model_validate(u) for u in users],
            page=page,
            total=total,
        )


@router.post("/users/{user_id}/disable", response_model=AdminUserPublic)
async def disable_user(user_id: uuid.UUID, _admin: AdminUser) -> AdminUserPublic:
    """Disable an account. Refuses to disable the last active admin (409)."""
    async with admin_session() as session:
        user = await _load_user(session, user_id)
        is_last_admin = (
            user.role is UserRole.admin
            and user.status is UserStatus.active
            and await _count_active_admins(session) <= 1
        )
        if is_last_admin:
            raise api_error(409, "last_admin", "Cannot disable the last admin.")
        user.status = UserStatus.disabled
        user.token_version = user.token_version + 1  # instant global logout
        await session.flush()
        return AdminUserPublic.model_validate(user)


@router.post("/users/{user_id}/promote", response_model=AdminUserPublic)
async def promote_user(user_id: uuid.UUID, _admin: AdminUser) -> AdminUserPublic:
    """Promote a user to admin."""
    async with admin_session() as session:
        user = await _load_user(session, user_id)
        user.role = UserRole.admin
        await session.flush()
        return AdminUserPublic.model_validate(user)


@router.post("/users/{user_id}/demote", response_model=AdminUserPublic)
async def demote_user(user_id: uuid.UUID, _admin: AdminUser) -> AdminUserPublic:
    """Demote an admin to user. Refuses to demote the last active admin (409)."""
    async with admin_session() as session:
        user = await _load_user(session, user_id)
        if user.role is UserRole.admin and await _count_active_admins(session) <= 1:
            raise api_error(409, "last_admin", "Cannot demote the last admin.")
        user.role = UserRole.user
        await session.flush()
        return AdminUserPublic.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, _admin: AdminUser) -> Response:
    """Delete a user (cascades all tenant data). Refuses the last admin (409)."""
    async with admin_session() as session:
        user = await _load_user(session, user_id)
        if user.role is UserRole.admin and await _count_active_admins(session) <= 1:
            raise api_error(409, "last_admin", "Cannot delete the last admin.")
        await session.delete(user)
        await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Registrations (approval queue)
# --------------------------------------------------------------------------- #


@router.get("/registrations/pending", response_model=list[AdminUserPublic])
async def pending_registrations(_admin: AdminUser) -> list[AdminUserPublic]:
    """List accounts awaiting approval (status=pending)."""
    async with admin_session() as session:
        result = await session.execute(
            select(User).where(User.status == UserStatus.pending).order_by(User.created_at)
        )
        return [AdminUserPublic.model_validate(u) for u in result.scalars().all()]


@router.post("/registrations/{user_id}/approve", response_model=AdminUserPublic)
async def approve_registration(user_id: uuid.UUID, _admin: AdminUser) -> AdminUserPublic:
    """Approve a pending account -> active."""
    async with admin_session() as session:
        user = await _load_user(session, user_id)
        if user.status is not UserStatus.pending:
            raise api_error(409, "not_pending", "Account is not pending approval.")
        user.status = UserStatus.active
        await session.flush()
        return AdminUserPublic.model_validate(user)


@router.post("/registrations/{user_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_registration(user_id: uuid.UUID, _admin: AdminUser) -> Response:
    """Reject a pending account (deletes it)."""
    async with admin_session() as session:
        user = await _load_user(session, user_id)
        if user.status is not UserStatus.pending:
            raise api_error(409, "not_pending", "Account is not pending approval.")
        await session.delete(user)
        await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Invites
# --------------------------------------------------------------------------- #


@router.post("/invites", response_model=InviteCreateResponse)
async def create_invite(payload: InviteCreateRequest, admin: AdminUser) -> InviteCreateResponse:
    """Create an invite. The token is shown ONCE (copy-the-URL delivery)."""
    raw = generate_refresh_token()
    expires = _now() + timedelta(days=INVITE_TTL_DAYS)
    async with admin_session() as session:
        invite = Invite(
            token_hash=hash_refresh_token(raw),
            email=str(payload.email) if payload.email else None,
            role=payload.role,
            created_by=admin.id,
            expires_at=expires,
        )
        session.add(invite)
        await session.flush()
        invite_id = invite.id
    return InviteCreateResponse(id=invite_id, token=raw, role=payload.role, expires_at=expires)


@router.get("/invites", response_model=list[InvitePublic])
async def list_invites(_admin: AdminUser) -> list[InvitePublic]:
    """List invites (never the token; only metadata)."""
    async with admin_session() as session:
        result = await session.execute(select(Invite).order_by(Invite.created_at.desc()))
        return [InvitePublic.model_validate(i) for i in result.scalars().all()]


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invite(invite_id: uuid.UUID, _admin: AdminUser) -> Response:
    """Revoke an invite."""
    async with admin_session() as session:
        result = await session.execute(select(Invite).where(Invite.id == invite_id))
        invite = result.scalar_one_or_none()
        if invite is not None:
            await session.delete(invite)
            await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Usage (time-series)
# --------------------------------------------------------------------------- #


@router.get("/usage", response_model=UsageResponse)
async def usage(
    _admin: AdminUser,
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: Annotated[str | None, Query()] = None,
    user_id: Annotated[uuid.UUID | None, Query()] = None,
    group_by: Annotated[str, Query()] = "day",
) -> UsageResponse:
    """Usage time-series across all users (admin metadata read).

    ``group_by`` is ``day`` (default) or ``month``; ``from``/``to`` bound the
    window (ISO date). Aggregates the append-only ``usage_events``.
    """
    trunc = "month" if group_by == "month" else "day"
    async with admin_session() as session:
        bucket = func.to_char(func.date_trunc(trunc, UsageEvent.created_at), "YYYY-MM-DD").label(
            "bucket"
        )
        stmt = (
            select(
                bucket,
                func.coalesce(func.sum(UsageEvent.tokens_in), 0),
                func.coalesce(func.sum(UsageEvent.tokens_out), 0),
            )
            .group_by(bucket)
            .order_by(bucket)
        )
        if user_id is not None:
            stmt = stmt.where(UsageEvent.user_id == user_id)
        from_dt = _parse_date(from_)
        to_dt = _parse_date(to)
        if from_dt is not None:
            stmt = stmt.where(UsageEvent.created_at >= from_dt)
        if to_dt is not None:
            stmt = stmt.where(UsageEvent.created_at <= to_dt)
        rows = (await session.execute(stmt)).all()
    return UsageResponse(
        series=[
            UsagePoint(bucket=b, tokens_in=int(ti), tokens_out=int(to_)) for (b, ti, to_) in rows
        ]
    )


# --------------------------------------------------------------------------- #
# Per-user quota
# --------------------------------------------------------------------------- #


@router.get("/users/{user_id}/quota", response_model=QuotaPublic)
async def get_quota(user_id: uuid.UUID, _admin: AdminUser) -> QuotaPublic:
    """Read a user's shared-key quota (install default if no row)."""
    async with admin_session() as session:
        await _load_user(session, user_id)
        result = await session.execute(select(UserQuota).where(UserQuota.user_id == user_id))
        quota = result.scalar_one_or_none()
        if quota is None:
            return QuotaPublic()
        return QuotaPublic.model_validate(quota)


@router.put("/users/{user_id}/quota", response_model=QuotaPublic)
async def set_quota(user_id: uuid.UUID, payload: QuotaUpdate, _admin: AdminUser) -> QuotaPublic:
    """Upsert a user's shared-key quota knobs."""
    async with admin_session() as session:
        await _load_user(session, user_id)
        result = await session.execute(select(UserQuota).where(UserQuota.user_id == user_id))
        quota = result.scalar_one_or_none()
        if quota is None:
            quota = UserQuota(user_id=user_id)
            session.add(quota)
        if payload.monthly_token_limit is not None:
            quota.monthly_token_limit = payload.monthly_token_limit
        if payload.requests_per_day is not None:
            quota.requests_per_day = payload.requests_per_day
        if payload.hard_disabled is not None:
            quota.hard_disabled = payload.hard_disabled
        await session.flush()
        return QuotaPublic.model_validate(quota)


# --------------------------------------------------------------------------- #
# Per-user key oversight (metadata only — NEVER secrets)
# --------------------------------------------------------------------------- #


@router.get("/users/{user_id}/keys", response_model=list[KeyMetadataPublic])
async def user_keys(user_id: uuid.UUID, _admin: AdminUser) -> list[KeyMetadataPublic]:
    """List a user's BYOK keys as fingerprints only (NEVER ciphertext/plaintext)."""
    async with admin_session() as session:
        await _load_user(session, user_id)
        result = await session.execute(select(ProviderKey).where(ProviderKey.user_id == user_id))
        return [
            KeyMetadataPublic(
                provider=row.provider,
                fingerprint=row.key_fingerprint,
                valid=row.is_active,
                checked_at=row.updated_at,
            )
            for row in result.scalars().all()
        ]


# --------------------------------------------------------------------------- #
# Operator default key (fingerprint only; rotate)
# --------------------------------------------------------------------------- #


@router.get("/operator-key", response_model=OperatorKeyPublic)
async def get_operator_key(_admin: AdminUser) -> OperatorKeyPublic:
    """Operator-default key metadata (fingerprint only; never the secret)."""
    async with admin_session() as session:
        result = await session.execute(
            select(OperatorDefault).where(OperatorDefault.provider == Provider.google.value)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise api_error(404, "not_configured", "No operator key configured.")
        return OperatorKeyPublic(
            provider=row.provider,
            fingerprint=row.key_fingerprint,
            key_version=row.key_version,
        )


@router.put("/operator-key", response_model=OperatorKeyPublic)
async def rotate_operator_key(
    payload: OperatorKeyRotateRequest, _admin: AdminUser
) -> OperatorKeyPublic:
    """Rotate the operator-default Gemini key (fingerprint returned, not the key)."""
    # Validate the value is a parseable string (no echo of the secret anywhere).
    _ = crypto.fingerprint(payload.api_key)
    async with admin_session() as session:
        row = await seed_operator_default(session, payload.api_key, provider=Provider.google.value)
        return OperatorKeyPublic(
            provider=row.provider,
            fingerprint=row.key_fingerprint,
            key_version=row.key_version,
        )


__all__ = ["router"]
