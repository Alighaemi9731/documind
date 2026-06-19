"""Documents API + /api/config (HTTP layer, tenant-scoped).

Upload -> queued + ingest_job; dedupe/idempotency; list; cross-tenant isolation;
delete; and the public /api/config shape. Uses the in-process ASGI client like
the Phase-1 project API tests.
"""

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
TEXT_FILE = ("hello world\nسلام دنیا\n" * 5).encode("utf-8")


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


async def _project(client: AsyncClient, h: dict[str, str]) -> str:
    created = await client.post("/api/projects", json={"name": "Docs"}, headers=h)
    assert created.status_code == 201
    body = created.json()
    # Project creation pins the Gemini embedding identity (ADR-0014).
    assert body["embedding_provider"] == "google"
    assert body["embedding_dim"] == 768
    return body["id"]


async def test_config_shape(client: AsyncClient) -> None:
    resp = await client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"max_upload_mb", "registration_mode"}
    assert isinstance(body["max_upload_mb"], int)


async def test_upload_then_list_and_dedupe(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    h = {"Authorization": f"Bearer {token}"}
    pid = await _project(client, h)

    files = {"files": ("notes.txt", TEXT_FILE, "text/plain")}
    up = await client.post(f"/api/projects/{pid}/documents", files=files, headers=h)
    assert up.status_code == 201
    items = up.json()
    assert len(items) == 1
    assert items[0]["status"] == "queued"
    assert items[0]["dedupe"] is False
    doc_id = items[0]["document_id"]

    # Re-uploading identical content dedupes to the same document.
    up2 = await client.post(
        f"/api/projects/{pid}/documents",
        files={"files": ("notes-copy.txt", TEXT_FILE, "text/plain")},
        headers=h,
    )
    assert up2.json()[0]["dedupe"] is True
    assert up2.json()[0]["document_id"] == doc_id

    listed = await client.get(f"/api/projects/{pid}/documents", headers=h)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == doc_id


async def test_upload_bad_type_returns_error_code(client: AsyncClient) -> None:
    token = await _token(client, "owner2@example.com")
    h = {"Authorization": f"Bearer {token}"}
    pid = await _project(client, h)

    files = {"files": ("evil.exe", b"MZ\x90\x00binary", "application/octet-stream")}
    up = await client.post(f"/api/projects/{pid}/documents", files=files, headers=h)
    assert up.status_code == 201  # per-file outcome, not a request failure
    assert up.json()[0]["error_code"] == "BAD_TYPE"
    assert up.json()[0]["document_id"] is None


async def test_cross_tenant_document_isolation(client: AsyncClient) -> None:
    ta = await _token(client, "a@example.com")
    tb = await _token(client, "b@example.com")
    ha = {"Authorization": f"Bearer {ta}"}
    hb = {"Authorization": f"Bearer {tb}"}
    pid = await _project(client, ha)

    await client.post(
        f"/api/projects/{pid}/documents",
        files={"files": ("a.txt", TEXT_FILE, "text/plain")},
        headers=ha,
    )

    # B cannot reach A's project documents (404 to avoid an existence oracle).
    b_list = await client.get(f"/api/projects/{pid}/documents", headers=hb)
    assert b_list.status_code == 404


async def test_delete_document(client: AsyncClient) -> None:
    token = await _token(client, "owner3@example.com")
    h = {"Authorization": f"Bearer {token}"}
    pid = await _project(client, h)
    up = await client.post(
        f"/api/projects/{pid}/documents",
        files={"files": ("a.txt", TEXT_FILE, "text/plain")},
        headers=h,
    )
    doc_id = up.json()[0]["document_id"]

    deleted = await client.delete(f"/api/projects/{pid}/documents/{doc_id}", headers=h)
    assert deleted.status_code == 204

    listed = await client.get(f"/api/projects/{pid}/documents", headers=h)
    assert listed.json() == []
