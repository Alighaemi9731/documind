"""Tenant-isolation integration tests (highest priority).

Proves, against a real RLS-FORCEd Postgres connected as a NON-superuser role:
- a tenant scope only ever returns the owner's rows;
- user A cannot read user B's project (empty / not found);
- the stale-GUC leak is closed: reusing one pooled connection across two
  users never lets B see A's rows;
- the GUC assertion fails hard when the connection is not scoped.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core.db import (
    admin_session,
    assert_guc,
    get_sessionmaker,
    tenant_session,
)
from app.models.project import Project
from app.models.user import User
from app.security.scoping import TenantScope

pytestmark = pytest.mark.asyncio


async def _make_user() -> uuid.UUID:
    uid = uuid.uuid4()
    async with admin_session() as session:
        session.add(User(id=uid, email=f"{uid}@example.com"))
        await session.flush()
    return uid


async def _make_project(owner_id: uuid.UUID, name: str) -> uuid.UUID:
    async with tenant_session(owner_id) as session:
        scope = TenantScope(session, owner_id)
        project = Project(owner_id=owner_id, name=name)
        await scope.add(project)
        return project.id


async def test_scope_returns_only_owner_rows(app_db: None) -> None:
    a = await _make_user()
    b = await _make_user()
    await _make_project(a, "A-project")
    await _make_project(b, "B-project")

    async with tenant_session(a) as session:
        a_projects = await TenantScope(session, a).list(Project)
    assert [p.name for p in a_projects] == ["A-project"]

    async with tenant_session(b) as session:
        b_projects = await TenantScope(session, b).list(Project)
    assert [p.name for p in b_projects] == ["B-project"]


async def test_a_cannot_read_bs_project(app_db: None) -> None:
    a = await _make_user()
    b = await _make_user()
    b_project_id = await _make_project(b, "secret")

    async with tenant_session(a) as session:
        found = await TenantScope(session, a).get(Project, b_project_id)
    assert found is None


async def test_pooled_connection_stale_guc_leak_is_closed(app_db: None) -> None:
    """Reuse ONE pooled connection across two users; B must never see A's rows.

    We force the engine pool down to a single connection so both transactions
    are guaranteed to land on the same physical connection. If the GUC ever
    leaked across the pool checkin, B's query would return A's project.
    """
    a = await _make_user()
    b = await _make_user()
    await _make_project(a, "A-only")

    maker = get_sessionmaker()

    # Transaction 1: scoped to A on a pooled connection.
    async with maker() as session, session.begin():
        await session.execute(
            text("SELECT set_config(:k,:v,true)"),
            {"k": "app.current_user_id", "v": str(a)},
        )
        a_rows = (await session.execute(TenantScope(session, a).select(Project))).scalars().all()
    assert [p.name for p in a_rows] == ["A-only"]

    # Transaction 2: scoped to B, very likely on the SAME pooled connection.
    async with maker() as session, session.begin():
        await session.execute(
            text("SELECT set_config(:k,:v,true)"),
            {"k": "app.current_user_id", "v": str(b)},
        )
        await assert_guc(session, b)
        b_rows = (await session.execute(TenantScope(session, b).select(Project))).scalars().all()
    assert b_rows == []  # B sees nothing of A's, even on a reused connection.


async def test_assert_guc_fails_hard_when_unscoped(app_db: None) -> None:
    a = await _make_user()
    maker = get_sessionmaker()
    async with maker() as session, session.begin():
        # No GUC set for this transaction.
        with pytest.raises(RuntimeError):
            await assert_guc(session, a)
