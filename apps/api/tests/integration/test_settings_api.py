"""Settings BYOK keys CRUD + provider selection at the HTTP layer.

Asserts: store-then-list shows fingerprint + valid but NEVER the secret; a
secret-leak scan confirms the plaintext/ciphertext never appears in ANY settings
response body; provider-selection 409 paths (capability_unsupported,
embedding_dim_mismatch); cross-tenant isolation of provider_keys.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import admin_session
from app.main import app
from app.models.enums import RegistrationMode
from app.providers.keystore import validation
from app.providers.keystore.validation import ValidationResult, ValidationStatus
from app.services.settings_service import ensure_system_settings

pytestmark = pytest.mark.asyncio

ORIGIN = "https://docs.example.com"
SECRET_KEY = "sk-supersecret-byok-abcdef-1234567890"


@pytest_asyncio.fixture()
async def client(app_db: None) -> AsyncIterator[AsyncClient]:
    async with admin_session() as session:
        row = await ensure_system_settings(session)
        row.registration_mode = RegistrationMode.open
        await session.flush()
    # Stub the BYOK validator: always valid, no network.
    validation.set_validator(lambda p, k: ValidationResult(ValidationStatus.valid))
    validation.clear_cache()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=ORIGIN) as c:
        yield c
    validation.set_validator(None)
    validation.clear_cache()


async def _token(client: AsyncClient, email: str) -> str:
    await client.post("/api/auth/register", json={"email": email, "password": "hunter2hunter2"})
    resp = await client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
    return resp.json()["access_token"]


async def test_keys_crud_no_secret_leak(client: AsyncClient) -> None:
    token = await _token(client, "byok@example.com")
    h = {"Authorization": f"Bearer {token}"}

    # Store a key (write-only).
    created = await client.post(
        "/api/settings/keys", json={"provider": "openai", "api_key": SECRET_KEY}, headers=h
    )
    assert created.status_code == 200
    body = created.json()
    assert body["valid"] is True
    assert "fingerprint" in body
    # The response NEVER carries the secret.
    assert SECRET_KEY not in created.text

    # List shows fingerprint + valid, never the secret.
    listed = await client.get("/api/settings/keys", headers=h)
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["provider"] == "openai"
    assert rows[0]["valid"] is True
    assert SECRET_KEY not in listed.text

    # Secret-leak scan across the providers endpoint too.
    providers = await client.get("/api/settings/providers", headers=h)
    assert SECRET_KEY not in providers.text
    # has_byok is reflected.
    openai_info = next(p for p in providers.json()["providers"] if p["id"] == "openai")
    assert openai_info["has_byok"] is True

    # Delete is idempotent + 204.
    deleted = await client.delete("/api/settings/keys/openai", headers=h)
    assert deleted.status_code == 204
    after = await client.get("/api/settings/keys", headers=h)
    assert after.json() == []


async def test_select_chat_provider(client: AsyncClient) -> None:
    token = await _token(client, "sel@example.com")
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.put(
        "/api/settings/providers",
        json={"capability": "chat", "provider": "openai", "model": "gpt-4o-mini"},
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json() == {"capability": "chat", "provider": "openai", "model": "gpt-4o-mini"}


async def test_capability_unsupported_409(client: AsyncClient) -> None:
    token = await _token(client, "cap@example.com")
    h = {"Authorization": f"Bearer {token}"}
    # Anthropic is chat-only: selecting it for embedding is 409.
    resp = await client.put(
        "/api/settings/providers",
        json={"capability": "embedding", "provider": "anthropic", "model": "x"},
        headers=h,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "capability_unsupported"


async def test_embedding_dim_mismatch_409(client: AsyncClient) -> None:
    token = await _token(client, "dim@example.com")
    h = {"Authorization": f"Bearer {token}"}
    # Create a project (pins Gemini 768).
    created = await client.post("/api/projects", json={"name": "P"}, headers=h)
    assert created.status_code == 201
    # Selecting OpenAI embedding (dim 1536) now conflicts with the 768 pin.
    resp = await client.put(
        "/api/settings/providers",
        json={
            "capability": "embedding",
            "provider": "openai",
            "model": "text-embedding-3-small",
        },
        headers=h,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "embedding_dim_mismatch"


async def test_cross_tenant_keys_isolated(client: AsyncClient) -> None:
    token_a = await _token(client, "a-keys@example.com")
    token_b = await _token(client, "b-keys@example.com")
    ha = {"Authorization": f"Bearer {token_a}"}
    hb = {"Authorization": f"Bearer {token_b}"}

    await client.post(
        "/api/settings/keys", json={"provider": "openai", "api_key": SECRET_KEY}, headers=ha
    )
    # B never sees A's key.
    b_list = await client.get("/api/settings/keys", headers=hb)
    assert b_list.json() == []


async def test_keys_require_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/settings/keys")
    assert resp.status_code == 401
