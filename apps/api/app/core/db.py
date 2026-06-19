"""Hardened async session factory — the chokepoint for tenant isolation.

Every tenant transaction runs through :func:`tenant_session` (request path) or
:func:`worker_tenant_session` (ingest worker). Both:

1. ``SET LOCAL app.current_user_id`` (and ``app.is_admin``) at txn start so
   Postgres RLS keys off the right tenant for the whole transaction.
2. ``RESET`` the GUCs when the connection returns to the pool
   (``reset_on_return='rollback'`` plus an explicit DISCARD/RESET), so a
   recycled pooled connection can NEVER inherit a previous tenant's id.
3. Provide :func:`assert_guc` to verify ``current_setting`` matches the
   expected uid before tenant queries and fail hard on mismatch.

``SET LOCAL`` is transaction-scoped, so it cannot leak across transactions on
its own; the explicit reset-on-checkin is belt-and-suspenders for driver edge
cases (ADR-0002).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# GUC names used by the RLS policies. Keep in sync with the Alembic migration.
GUC_USER_ID = "app.current_user_id"
GUC_IS_ADMIN = "app.is_admin"

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _install_reset_listener(engine: AsyncEngine) -> None:
    """RESET tenant GUCs when a connection is checked back into the pool.

    Runs on the sync DBAPI connection underneath the async engine. We issue a
    plain ``RESET`` for both GUCs so the next checkout starts clean even if a
    transaction failed to unwind ``SET LOCAL`` for any reason.
    """

    @event.listens_for(engine.sync_engine, "checkin")
    def _reset_guc(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        try:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute(f"RESET {GUC_USER_ID}")
                cursor.execute(f"RESET {GUC_IS_ADMIN}")
            finally:
                cursor.close()
        except Exception:
            # If the connection is already broken, invalidate rather than
            # return a possibly-dirty connection to the pool.
            connection_record.invalidate()


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use.

    ``reset_on_return='rollback'`` guarantees any open transaction (and its
    ``SET LOCAL`` GUCs) is unwound on checkin; the checkin listener then
    explicitly RESETs the GUCs as a fail-safe.
    """
    global _engine, _sessionmaker
    if _engine is None:
        engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_reset_on_return="rollback",
        )
        _install_reset_listener(engine)
        _engine = engine
        _sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the configured sessionmaker (initializing the engine if needed)."""
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None  # noqa: S101 - invariant after get_engine
    return _sessionmaker


async def dispose_engine() -> None:
    """Dispose the engine (lifespan shutdown / test teardown)."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def assert_guc(session: AsyncSession, expected_user_id: uuid.UUID) -> None:
    """Verify the connection's tenant GUC matches ``expected_user_id``.

    Fails hard (raises) on mismatch rather than silently returning wrong/empty
    rows. Call before issuing tenant queries.
    """
    result = await session.execute(text(f"SELECT current_setting('{GUC_USER_ID}', true)"))
    current = result.scalar()
    if current != str(expected_user_id):
        raise RuntimeError("Tenant GUC mismatch: connection is not scoped to the expected user.")


async def _set_tenant_guc(session: AsyncSession, user_id: uuid.UUID, *, is_admin: bool) -> None:
    """Issue ``SET LOCAL`` for the tenant GUCs inside the current transaction.

    ``set_config(..., true)`` is the local (transaction-scoped) form and binds
    parameters safely (no SQL string interpolation of the uid).
    """
    await session.execute(
        text("SELECT set_config(:k, :v, true)"),
        {"k": GUC_USER_ID, "v": str(user_id)},
    )
    await session.execute(
        text("SELECT set_config(:k, :v, true)"),
        {"k": GUC_IS_ADMIN, "v": "true" if is_admin else "false"},
    )


@asynccontextmanager
async def tenant_session(
    user_id: uuid.UUID, *, is_admin: bool = False
) -> AsyncIterator[AsyncSession]:
    """Yield a session inside a transaction scoped to ``user_id``.

    The transaction is committed on clean exit and rolled back on exception.
    Used by request handlers (via ``get_tenant_session``) and reusable for any
    code path that must read/write tenant data.
    """
    maker = get_sessionmaker()
    async with maker() as session, session.begin():
        await _set_tenant_guc(session, user_id, is_admin=is_admin)
        await assert_guc(session, user_id)
        yield session


@asynccontextmanager
async def worker_tenant_session(owner_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """Worker-context tenant session: sets the GUC from ``job.owner_id``.

    Identical isolation guarantees as :func:`tenant_session` but never grants
    the admin bypass (workers operate strictly as the owning tenant).
    """
    async with tenant_session(owner_id, is_admin=False) as session:
        yield session


@asynccontextmanager
async def admin_session() -> AsyncIterator[AsyncSession]:
    """A session for non-tenant auth/metadata work (login, registration, refresh).

    These operations precede a tenant identity (e.g. looking up a user by email
    during login) and must read/write the ``users`` / ``auth_identities`` /
    ``refresh_tokens`` / ``invites`` metadata tables across users. Because RLS
    is FORCED on ``users``/``projects``, this session sets the RLS metadata
    bypass GUC (``app.is_admin='true'``). That bypass is granted ONLY on these
    metadata tables and is never created for any document/chunk content table.
    """
    maker = get_sessionmaker()
    async with maker() as session, session.begin():
        await session.execute(
            text("SELECT set_config(:k, :v, true)"),
            {"k": GUC_IS_ADMIN, "v": "true"},
        )
        yield session


__all__ = [
    "GUC_USER_ID",
    "GUC_IS_ADMIN",
    "get_engine",
    "get_sessionmaker",
    "dispose_engine",
    "assert_guc",
    "tenant_session",
    "worker_tenant_session",
    "admin_session",
]
