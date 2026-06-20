"""Auth domain logic: registration, login, refresh rotation, logout.

Tenant-isolation note: these operations run on a NON-tenant session
(:func:`app.core.db.admin_session`) because they manipulate ``users`` /
``auth_identities`` / ``refresh_tokens`` *before* a tenant identity exists or
across the whole account. They never read another user's tenant data.

Security properties enforced here:
- argon2id hashing, rehash-on-login, semaphore-bounded to cap RAM under a flood.
- NFC + lowercase email normalization (matches the CITEXT unique column).
- Refresh tokens are opaque, stored only as sha256, rotated every use, grouped
  into a ``family_id``; reuse of an already-used token revokes the whole family
  (ADR-0001). A short grace window tolerates the immediately-prior token.
"""

from __future__ import annotations

import asyncio
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    password_needs_rehash,
    verify_password,
)
from app.models.auth_identity import PASSWORD_PROVIDER, AuthIdentity
from app.models.enums import RegistrationMode, UserRole, UserStatus
from app.models.invite import Invite
from app.models.refresh_token import RefreshToken
from app.models.user import User

# Bound concurrent argon2 hashes so a login/registration flood cannot OOM a
# 2GB box (each hash is ~64 MiB). Process-local; one uvicorn worker.
_ARGON2_SEMAPHORE = asyncio.Semaphore(3)

# Accept the immediately-prior (just-rotated) token for this many seconds to
# avoid multi-tab false lockouts (client also single-flights).
REFRESH_GRACE_SECONDS = 10


class AuthError(Exception):
    """Domain-level auth failure with a stable machine code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class RegistrationPending(Exception):
    """Raised when approval-mode registration succeeds but needs admin review."""

    def __init__(self, user: User) -> None:
        super().__init__("registration pending approval")
        self.user = user


@dataclass
class IssuedRefresh:
    """A freshly minted refresh token (plaintext) plus its DB row."""

    token: str
    row: RefreshToken


def normalize_email(email: str) -> str:
    """NFC-normalize and lowercase an email to match the CITEXT unique key."""
    return unicodedata.normalize("NFC", email).strip().lower()


def _now() -> datetime:
    return datetime.now(UTC)


async def _hash_password_bounded(password: str) -> str:
    async with _ARGON2_SEMAPHORE:
        return await asyncio.to_thread(hash_password, password)


async def _verify_password_bounded(encoded: str, password: str) -> bool:
    async with _ARGON2_SEMAPHORE:
        return await asyncio.to_thread(verify_password, encoded, password)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    norm = normalize_email(email)
    result = await session.execute(select(User).where(User.email == norm))
    return result.scalar_one_or_none()


async def _password_identity(session: AsyncSession, user_id: uuid.UUID) -> AuthIdentity | None:
    result = await session.execute(
        select(AuthIdentity).where(
            AuthIdentity.user_id == user_id,
            AuthIdentity.provider == PASSWORD_PROVIDER,
        )
    )
    return result.scalar_one_or_none()


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #


async def _consume_invite(session: AsyncSession, raw_token: str, email: str) -> Invite:
    """Validate + atomically consume an invite, returning it. Raises on failure."""
    token_hash = hash_refresh_token(raw_token)
    result = await session.execute(select(Invite).where(Invite.token_hash == token_hash))
    invite = result.scalar_one_or_none()
    if invite is None or invite.consumed_at is not None:
        raise AuthError("invite_invalid", "Invite is invalid or already used.")
    if invite.expires_at <= _now():
        raise AuthError("invite_invalid", "Invite has expired.")
    if invite.email is not None and normalize_email(invite.email) != email:
        raise AuthError("invite_invalid", "Invite does not match this email.")
    return invite


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    registration_mode: RegistrationMode,
    invite_token: str | None,
    admin_email: str | None = None,
) -> User:
    """Create a user honoring REGISTRATION_MODE. Raises on conflict/forbidden.

    Returns the created (or reconciled) user. In approval mode raises
    :class:`RegistrationPending` so the route can emit 202. The bootstrap
    ``admin_email`` self-registration is reconciled to an admin account.
    """
    norm_email = normalize_email(email)
    existing = await get_user_by_email(session, norm_email)
    if existing is not None:
        # `bootstrap-admin` creates the configured admin account WITHOUT a
        # password (no password identity). Let that exact email CLAIM the account
        # on first self-registration: set the password and keep it an active
        # admin. This is the only passwordless account in v1, and the claim is
        # scoped to the configured admin email — every other existing email is a
        # genuine duplicate. Mode (open/approval/invite) is bypassed for the
        # operator's own admin, mirroring the new-account reconciliation below.
        is_admin_email = bool(admin_email and normalize_email(admin_email) == norm_email)
        has_password = await _password_identity(session, existing.id) is not None
        if is_admin_email and not has_password:
            existing.role = UserRole.admin
            existing.status = UserStatus.active
            session.add(
                AuthIdentity(
                    user_id=existing.id,
                    provider=PASSWORD_PROVIDER,
                    provider_subject=norm_email,
                    password_hash=await _hash_password_bounded(password),
                )
            )
            await session.flush()
            return existing
        raise AuthError("email_taken", "Email already registered.")

    invite: Invite | None = None
    status = UserStatus.active
    role = UserRole.user
    source = registration_mode.value

    if registration_mode is RegistrationMode.invite:
        if not invite_token:
            raise AuthError("invite_required", "An invite token is required.")
        invite = await _consume_invite(session, invite_token, norm_email)
        role = invite.role
        source = "invite"
    elif registration_mode is RegistrationMode.approval:
        status = UserStatus.pending

    # Bootstrap-admin reconciliation: the configured admin email is always an
    # active admin even if it self-registers.
    if admin_email and normalize_email(admin_email) == norm_email:
        role = UserRole.admin
        status = UserStatus.active

    password_hash = await _hash_password_bounded(password)

    user = User(
        email=norm_email,
        role=role,
        status=status,
        registration_source=source,
    )
    session.add(user)
    await session.flush()

    session.add(
        AuthIdentity(
            user_id=user.id,
            provider=PASSWORD_PROVIDER,
            provider_subject=norm_email,
            password_hash=password_hash,
        )
    )

    if invite is not None:
        invite.consumed_at = _now()
        invite.consumed_by = user.id

    await session.flush()

    if status is UserStatus.pending:
        raise RegistrationPending(user)
    return user


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    """Verify credentials. Generic failure (no user-enumeration oracle).

    On success, transparently rehashes the password if params are outdated and
    enforces the account status gate (pending/disabled -> 403-style codes).
    """
    user = await get_user_by_email(session, email)
    identity = await _password_identity(session, user.id) if user is not None else None

    # Always run a verify to keep timing roughly uniform regardless of whether
    # the user exists (mitigates enumeration via response time).
    stored_hash = identity.password_hash if identity and identity.password_hash else None
    ok = await _verify_password_bounded(
        stored_hash
        or "$argon2id$v=19$m=65536,t=2,p=2$AAAAAAAAAAAAAAAAAAAAAA$"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        password,
    )

    if user is None or identity is None or stored_hash is None or not ok:
        raise AuthError("invalid_credentials", "Invalid email or password.")

    if user.status is UserStatus.pending:
        raise AuthError("account_pending", "Account is pending approval.")
    if user.status is UserStatus.disabled:
        raise AuthError("account_disabled", "Account is disabled.")

    if password_needs_rehash(stored_hash):
        identity.password_hash = await _hash_password_bounded(password)
        await session.flush()

    return user


# --------------------------------------------------------------------------- #
# Refresh-token issuance / rotation
# --------------------------------------------------------------------------- #


async def issue_refresh_token(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    family_id: uuid.UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> IssuedRefresh:
    """Mint + persist a new refresh token (hashed). Starts a new family if none."""
    raw = generate_refresh_token()
    row = RefreshToken(
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        token_hash=hash_refresh_token(raw),
        expires_at=_now() + timedelta(days=settings.refresh_token_ttl_days),
        ip=ip,
        user_agent=user_agent,
    )
    session.add(row)
    await session.flush()
    return IssuedRefresh(token=raw, row=row)


async def _revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
        )
    )
    now = _now()
    for row in result.scalars().all():
        row.revoked_at = now
    await session.flush()


async def _family_chain_advanced(session: AsyncSession, row: RefreshToken) -> bool:
    """True if a newer token in the same family has already been used.

    Indicates the legitimate refresh chain has progressed beyond ``row``; a
    re-presentation of ``row`` is then a stale/leaked replay (revoke the
    family), not a benign in-grace multi-tab race.
    """
    result = await session.execute(
        select(RefreshToken.id).where(
            RefreshToken.family_id == row.family_id,
            RefreshToken.id != row.id,
            RefreshToken.issued_at >= row.used_at,
            RefreshToken.used_at.is_not(None),
        )
    )
    return result.first() is not None


async def rotate_refresh_token(
    session: AsyncSession,
    *,
    raw_token: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, IssuedRefresh]:
    """Validate + rotate a refresh token. Detect reuse -> revoke family + 401.

    Returns the owning user and a freshly-issued token (same family). A token
    presented after it was already rotated is reuse: the whole family is
    revoked and an error is raised. A short grace window tolerates the exact
    immediately-prior token (multi-tab single-flight races).
    """
    token_hash = hash_refresh_token(raw_token)
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()

    if row is None:
        raise AuthError("refresh_invalid", "Refresh token is invalid.")

    now = _now()

    if row.revoked_at is not None:
        # Presenting a revoked token => treat the family as compromised.
        await _revoke_family(session, row.family_id)
        raise AuthError("refresh_reuse", "Refresh token reuse detected.")

    if row.expires_at <= now:
        raise AuthError("refresh_invalid", "Refresh token has expired.")

    if row.used_at is not None:
        # Already rotated. Within the grace window it's a benign race; the
        # original token has a successor and we accept the prior token once
        # more without minting a duplicate. Outside the window it's reuse.
        within_grace = (now - row.used_at) <= timedelta(seconds=REFRESH_GRACE_SECONDS)
        chain_advanced = await _family_chain_advanced(session, row)
        if not within_grace or chain_advanced:
            await _revoke_family(session, row.family_id)
            raise AuthError("refresh_reuse", "Refresh token reuse detected.")
        # Grace: re-issue against the same family without re-marking this row.
        user = await _load_active_user(session, row.user_id)
        issued = await issue_refresh_token(
            session,
            user_id=row.user_id,
            family_id=row.family_id,
            ip=ip,
            user_agent=user_agent,
        )
        return user, issued

    # Normal rotation: mark the token used (NOT revoked) and mint a successor
    # in-family. ``revoked_at`` is reserved for explicit/family revocation, so a
    # near-simultaneous second presentation of this same token falls into the
    # grace branch above (benign multi-tab race) rather than a false lockout.
    row.used_at = now
    user = await _load_active_user(session, row.user_id)
    issued = await issue_refresh_token(
        session,
        user_id=row.user_id,
        family_id=row.family_id,
        ip=ip,
        user_agent=user_agent,
    )
    return user, issued


async def _load_active_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthError("refresh_invalid", "Account no longer exists.")
    if user.status is UserStatus.disabled:
        raise AuthError("account_disabled", "Account is disabled.")
    return user


async def revoke_refresh_token(session: AsyncSession, *, raw_token: str) -> None:
    """Logout: revoke the presented token (and its family). Idempotent."""
    token_hash = hash_refresh_token(raw_token)
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        await _revoke_family(session, row.family_id)


__all__ = [
    "AuthError",
    "RegistrationPending",
    "IssuedRefresh",
    "normalize_email",
    "get_user_by_email",
    "register",
    "authenticate",
    "issue_refresh_token",
    "rotate_refresh_token",
    "revoke_refresh_token",
    "REFRESH_GRACE_SECONDS",
]
