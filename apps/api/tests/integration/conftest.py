"""Integration-test fixtures: a real Postgres (pgvector) with migrations + RLS.

Gated on a reachable ``DATABASE_URL``; if Postgres is unreachable every test in
this package is skipped (so local runs without Docker stay green while CI, which
provides Postgres, exercises the real isolation guarantees).

The schema is built by running the Alembic migration (so RLS policies, FORCE,
enums, and extensions match production exactly). Tests connect as a
non-superuser application role (``documind_app``) because superusers bypass RLS
even under FORCE — the leak test would be meaningless otherwise.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from types import ModuleType

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Settings must see a test env before import.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-please-change-0123456789abcdef-0123456789")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://documind:documind@localhost:5432/documind",
)

# A non-superuser role used by the application connections under test.
APP_ROLE = "documind_app"
APP_ROLE_PASSWORD = "ci-only-app-role-pw"  # throwaway test/CI credential, not a secret


def _app_database_url() -> str:
    """Rewrite DATABASE_URL to connect as the non-superuser application role."""
    # postgresql+asyncpg://user:pass@host:port/db -> swap the credentials.
    scheme, rest = DATABASE_URL.split("://", 1)
    _creds, hostpart = rest.split("@", 1)
    return f"{scheme}://{APP_ROLE}:{APP_ROLE_PASSWORD}@{hostpart}"


async def _postgres_reachable() -> bool:
    try:
        engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture(scope="session")
async def admin_engine() -> AsyncIterator[AsyncEngine]:
    """A superuser/owner engine used to build the schema and the app role."""
    if not await _postgres_reachable():
        pytest.skip("Postgres not reachable; skipping integration tests.")
    engine = create_async_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    yield engine
    await engine.dispose()


def _load_migration_file(filename: str, module_name: str) -> ModuleType:
    """Load a migration module directly from its file path.

    The filename starts with a digit and ``alembic/versions`` is not a package,
    so we load it by spec rather than a dotted import.
    """
    import importlib.util
    from pathlib import Path

    here = Path(__file__).resolve()
    mig_path = here.parents[2] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(module_name, mig_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_migration() -> ModuleType:
    """Load the Phase-1 migration module (back-compat helper)."""
    return _load_migration_file("0001_phase1_auth_tenancy.py", "phase1_migration")


def _load_phase2_migration() -> ModuleType:
    return _load_migration_file("0002_phase2_ingestion.py", "phase2_migration")


@pytest_asyncio.fixture(scope="session")
async def schema(admin_engine: AsyncEngine) -> AsyncIterator[None]:
    """Build the Phase-1 schema + RLS via the migration's upgrade() and create
    a non-superuser application role with table privileges."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    mig = _load_migration()
    mig2 = _load_phase2_migration()

    async with admin_engine.connect() as conn:
        await conn.run_sync(_drop_all)

        def _run_upgrade(sync_conn: Connection) -> None:
            ctx = MigrationContext.configure(sync_conn)
            with Operations.context(ctx):
                mig.upgrade()
                mig2.upgrade()

        await conn.run_sync(_run_upgrade)

        # Create the non-superuser app role + grant privileges.
        await conn.execute(text(f"DROP ROLE IF EXISTS {APP_ROLE}"))
        await conn.execute(text(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_ROLE_PASSWORD}'"))
        await conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
        await conn.execute(
            text(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"
            )
        )
        await conn.execute(text(f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}"))

    yield

    async with admin_engine.connect() as conn:
        await conn.run_sync(_drop_all)
        await conn.execute(text(f"DROP ROLE IF EXISTS {APP_ROLE}"))


def _drop_all(sync_conn: Connection) -> None:
    # asyncpg rejects multiple commands in one prepared statement; run separately.
    sync_conn.exec_driver_sql("DROP SCHEMA public CASCADE")
    sync_conn.exec_driver_sql("CREATE SCHEMA public")


@pytest_asyncio.fixture()
async def app_db(schema: None, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Point app.core.db at a fresh engine bound to the non-superuser role.

    Truncates the data tables between tests for isolation.
    """
    import app.core.db as db_module

    await db_module.dispose_engine()
    monkeypatch.setattr(db_module.settings, "database_url", _app_database_url())

    # Force engine recreation against the app role.
    db_module._engine = None
    db_module._sessionmaker = None
    db_module.get_engine()

    yield

    # Clean the data tables (admin engine bypasses RLS as owner/superuser).
    from sqlalchemy.ext.asyncio import create_async_engine as _cae

    cleaner = _cae(DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with cleaner.connect() as conn:
        await conn.execute(
            text(
                "TRUNCATE chunks, ingest_jobs, documents, operator_default, "
                "refresh_tokens, auth_identities, projects, "
                "invites, system_settings, users RESTART IDENTITY CASCADE"
            )
        )
    await cleaner.dispose()
    await db_module.dispose_engine()
