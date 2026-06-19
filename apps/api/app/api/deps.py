"""FastAPI dependency chain for auth + tenancy.

``get_current_user`` (decode Bearer, verify token_version against the DB)
-> ``get_current_active_user`` (status gate)
-> ``require_admin`` (role gate).

``get_tenant_session`` yields a session whose connection already issued
``SET LOCAL app.current_user_id`` for the current user; ``get_tenant_scope``
wraps it in a :class:`TenantScope`. Tenant handlers depend on these and never
touch the raw ORM directly.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import api_error
from app.core.db import admin_session, tenant_session
from app.core.security import TokenError, decode_access_token
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.security.scoping import TenantScope

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Decode the Bearer access token and load the user, checking token_version.

    A ``tv`` mismatch (token_version bumped since issuance) invalidates the
    token instantly — used for global logout / disable.
    """
    if credentials is None or not credentials.credentials:
        raise api_error(401, "not_authenticated", "Missing bearer token.")
    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise api_error(401, "invalid_token", "Invalid or expired token.") from exc

    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise api_error(401, "invalid_token", "Malformed token subject.") from exc

    async with admin_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if user is None:
        raise api_error(401, "invalid_token", "Account no longer exists.")
    if int(payload.get("tv", -1)) != user.token_version:
        raise api_error(401, "token_revoked", "Token has been revoked.")
    return user


async def get_current_active_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Reject non-active accounts (pending/disabled) with 403."""
    if user.status is not UserStatus.active:
        raise api_error(403, "account_inactive", "Account is not active.")
    return user


async def require_admin(
    user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Require the admin role; 403 otherwise."""
    if user.role is not UserRole.admin:
        raise api_error(403, "forbidden", "Admin privileges required.")
    return user


CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(require_admin)]


async def get_tenant_session(
    user: CurrentUser,
) -> AsyncIterator[AsyncSession]:
    """Yield a transaction-scoped session with the tenant GUC already set.

    The request path is ALWAYS tenant-scoped (``app.is_admin='false'``), even
    for admins: the RLS admin bypass must never apply to tenant *content*
    (projects, and Phase-2 documents/chunks) per ADR-0002. Cross-user admin
    operations use a dedicated metadata session (``admin_session``) on the
    allow-listed metadata tables only — never this dependency.
    """
    async with tenant_session(user.id, is_admin=False) as session:
        yield session


async def get_tenant_scope(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> TenantScope:
    """Yield a :class:`TenantScope` bound to the current user + scoped session."""
    return TenantScope(session, user.id)


def client_ip(request: Request) -> str:
    """Best-effort client IP for rate limiting (single trusted proxy = Caddy)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


TenantSession = Annotated[AsyncSession, Depends(get_tenant_session)]
TenantScopeDep = Annotated[TenantScope, Depends(get_tenant_scope)]


__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_admin",
    "get_tenant_session",
    "get_tenant_scope",
    "client_ip",
    "CurrentUser",
    "AdminUser",
    "TenantSession",
    "TenantScopeDep",
]
