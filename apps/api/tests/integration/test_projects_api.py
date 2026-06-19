"""Projects CRUD + cross-tenant isolation at the HTTP layer."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import admin_session
from app.main import app
from app.models.enums import RegistrationMode
from app.services.settings_service import ensure_system_settings

pytestmark = pytest.mark.asyncio

ORIGIN = "https://docs.example.com"


@pytest_asyncio.fixture()
async def client(app_db: None) -> AsyncIterator[AsyncClient]:
    async with admin_session() as session:
        row = await ensure_system_settings(session)
        row.registration_mode = RegistrationMode.open
        await session.flush()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=ORIGIN) as c:
        yield c


async def _token(client: AsyncClient, email: str) -> str:
    await client.post("/api/auth/register", json={"email": email, "password": "hunter2hunter2"})
    resp = await client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
    return resp.json()["access_token"]


async def test_project_crud_for_owner(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    h = {"Authorization": f"Bearer {token}"}

    created = await client.post("/api/projects", json={"name": "Docs"}, headers=h)
    assert created.status_code == 201
    pid = created.json()["id"]

    listed = await client.get("/api/projects", headers=h)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    got = await client.get(f"/api/projects/{pid}", headers=h)
    assert got.status_code == 200

    patched = await client.patch(f"/api/projects/{pid}", json={"description": "updated"}, headers=h)
    assert patched.status_code == 200
    assert patched.json()["description"] == "updated"

    deleted = await client.delete(f"/api/projects/{pid}", headers=h)
    assert deleted.status_code == 204

    gone = await client.get(f"/api/projects/{pid}", headers=h)
    assert gone.status_code == 404


async def test_user_b_cannot_access_user_a_project(client: AsyncClient) -> None:
    token_a = await _token(client, "a@example.com")
    token_b = await _token(client, "b@example.com")
    ha = {"Authorization": f"Bearer {token_a}"}
    hb = {"Authorization": f"Bearer {token_b}"}

    created = await client.post("/api/projects", json={"name": "A-secret"}, headers=ha)
    pid = created.json()["id"]

    # B's list never contains A's project.
    b_list = await client.get("/api/projects", headers=hb)
    assert b_list.json() == []

    # B's direct GET is 404 (not 403, to avoid existence oracle).
    b_get = await client.get(f"/api/projects/{pid}", headers=hb)
    assert b_get.status_code == 404

    # B cannot delete A's project.
    b_del = await client.delete(f"/api/projects/{pid}", headers=hb)
    assert b_del.status_code == 404


async def test_projects_require_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/projects")
    assert resp.status_code == 401
