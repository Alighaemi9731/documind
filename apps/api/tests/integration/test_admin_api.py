"""Admin endpoints at the HTTP layer (section 6/10).

Covers: list/disable/promote/demote + last-admin guard, usage, quota,
keys-metadata (fingerprint only, never secret), operator-key rotate; plus a
non-admin 403 on every admin route and cross-tenant key isolation.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import admin_session
from app.main import app
from app.models.enums import Provider, RegistrationMode, UserRole
from app.models.user import User
from app.providers.keystore import validation
from app.providers.keystore.operator_default import seed_operator_default
from app.providers.keystore.validation import ValidationResult, ValidationStatus
from app.services.settings_service import ensure_system_settings

pytestmark = pytest.mark.asyncio

ORIGIN = "https://docs.example.com"


@pytest_asyncio.fixture()
async def client(app_db: None) -> AsyncIterator[AsyncClient]:
    async with admin_session() as session:
        row = await ensure_system_settings(session)
        row.registration_mode = RegistrationMode.open
        await session.flush()
        # Seed an operator key so the operator-key endpoints have a row.
        await seed_operator_default(session, "AIza-operator-key", provider=Provider.google.value)
    validation.set_validator(lambda p, k: ValidationResult(ValidationStatus.valid))
    validation.clear_cache()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=ORIGIN) as c:
        yield c
    validation.set_validator(None)
    validation.clear_cache()


async def _register(client: AsyncClient, email: str) -> str:
    await client.post("/api/auth/register", json={"email": email, "password": "hunter2hunter2"})
    resp = await client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
    return resp.json()["access_token"]


async def _make_admin(email: str) -> uuid.UUID:
    async with admin_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.role = UserRole.admin
        await session.flush()
        return user.id


async def _admin_token(client: AsyncClient, email: str = "admin@example.com") -> str:
    await client.post("/api/auth/register", json={"email": email, "password": "hunter2hunter2"})
    await _make_admin(email)
    resp = await client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
    return resp.json()["access_token"]


async def test_non_admin_forbidden(client: AsyncClient) -> None:
    token = await _register(client, "plain@example.com")
    h = {"Authorization": f"Bearer {token}"}
    for path in ("/api/admin/users", "/api/admin/usage", "/api/admin/operator-key"):
        resp = await client.get(path, headers=h)
        assert resp.status_code == 403, path


async def test_list_and_promote_demote(client: AsyncClient) -> None:
    admin_token = await _admin_token(client)
    ha = {"Authorization": f"Bearer {admin_token}"}
    # Create a second user to operate on.
    await _register(client, "target@example.com")
    target_id = None
    async with admin_session() as session:
        result = await session.execute(select(User).where(User.email == "target@example.com"))
        target_id = result.scalar_one().id

    listed = await client.get("/api/admin/users", headers=ha)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 2

    promoted = await client.post(f"/api/admin/users/{target_id}/promote", headers=ha)
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"

    demoted = await client.post(f"/api/admin/users/{target_id}/demote", headers=ha)
    assert demoted.status_code == 200
    assert demoted.json()["role"] == "user"


async def test_last_admin_guard(client: AsyncClient) -> None:
    admin_token = await _admin_token(client, "solo-admin@example.com")
    ha = {"Authorization": f"Bearer {admin_token}"}
    admin_id = None
    async with admin_session() as session:
        result = await session.execute(select(User).where(User.email == "solo-admin@example.com"))
        admin_id = result.scalar_one().id

    # Cannot demote/disable/delete the only admin.
    demote = await client.post(f"/api/admin/users/{admin_id}/demote", headers=ha)
    assert demote.status_code == 409
    assert demote.json()["error"]["code"] == "last_admin"

    disable = await client.post(f"/api/admin/users/{admin_id}/disable", headers=ha)
    assert disable.status_code == 409

    delete = await client.delete(f"/api/admin/users/{admin_id}", headers=ha)
    assert delete.status_code == 409


async def test_quota_get_put(client: AsyncClient) -> None:
    admin_token = await _admin_token(client)
    ha = {"Authorization": f"Bearer {admin_token}"}
    await _register(client, "quotauser@example.com")
    async with admin_session() as session:
        result = await session.execute(select(User).where(User.email == "quotauser@example.com"))
        uid = result.scalar_one().id

    put = await client.put(
        f"/api/admin/users/{uid}/quota",
        json={"monthly_token_limit": 5000, "hard_disabled": True},
        headers=ha,
    )
    assert put.status_code == 200
    assert put.json()["monthly_token_limit"] == 5000
    assert put.json()["hard_disabled"] is True

    got = await client.get(f"/api/admin/users/{uid}/quota", headers=ha)
    assert got.json()["monthly_token_limit"] == 5000


async def test_user_keys_metadata_only(client: AsyncClient) -> None:
    admin_token = await _admin_token(client)
    ha = {"Authorization": f"Bearer {admin_token}"}
    user_token = await _register(client, "keyowner@example.com")
    secret = "sk-admin-scan-secret-9876543210"
    await client.post(
        "/api/settings/keys",
        json={"provider": "openai", "api_key": secret},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    async with admin_session() as session:
        result = await session.execute(select(User).where(User.email == "keyowner@example.com"))
        uid = result.scalar_one().id

    resp = await client.get(f"/api/admin/users/{uid}/keys", headers=ha)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["provider"] == "openai"
    assert "fingerprint" in rows[0]
    # The admin keys view NEVER carries the secret.
    assert secret not in resp.text


async def test_operator_key_rotate_fingerprint_only(client: AsyncClient) -> None:
    admin_token = await _admin_token(client)
    ha = {"Authorization": f"Bearer {admin_token}"}

    before = await client.get("/api/admin/operator-key", headers=ha)
    assert before.status_code == 200
    v0 = before.json()["key_version"]

    rotate = await client.put(
        "/api/admin/operator-key", json={"api_key": "AIza-rotated-key"}, headers=ha
    )
    assert rotate.status_code == 200
    assert rotate.json()["key_version"] == v0 + 1
    # The rotation response NEVER carries the new key.
    assert "AIza-rotated-key" not in rotate.text


async def test_usage_timeseries(client: AsyncClient) -> None:
    admin_token = await _admin_token(client)
    ha = {"Authorization": f"Bearer {admin_token}"}
    resp = await client.get("/api/admin/usage", headers=ha)
    assert resp.status_code == 200
    assert "series" in resp.json()


async def test_settings_non_admin_forbidden(client: AsyncClient) -> None:
    token = await _register(client, "settings-plain@example.com")
    h = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/api/admin/settings", headers=h)).status_code == 403
    assert (
        await client.put("/api/admin/settings", json={"signups_enabled": False}, headers=h)
    ).status_code == 403


async def test_settings_get_put_roundtrip(client: AsyncClient) -> None:
    admin_token = await _admin_token(client)
    ha = {"Authorization": f"Bearer {admin_token}"}

    got = await client.get("/api/admin/settings", headers=ha)
    assert got.status_code == 200
    body = got.json()
    assert body["registration_mode"] == "open"
    assert set(body["branding"]) == {"app_name", "accent_color", "logo_url"}
    assert "default_monthly_token_limit" in body

    put = await client.put(
        "/api/admin/settings",
        json={
            "registration_mode": "invite",
            "signups_enabled": False,
            "default_monthly_token_limit": 12345,
            "branding": {
                "app_name": "Acme Docs",
                "accent_color": "#1A2B3C",
                "logo_url": "/static/logo.svg",
            },
        },
        headers=ha,
    )
    assert put.status_code == 200
    updated = put.json()
    assert updated["registration_mode"] == "invite"
    assert updated["signups_enabled"] is False
    assert updated["default_monthly_token_limit"] == 12345
    assert updated["branding"]["app_name"] == "Acme Docs"
    assert updated["branding"]["accent_color"] == "#1A2B3C"
    assert updated["branding"]["logo_url"] == "/static/logo.svg"

    # Round-trip: GET reflects the persisted changes.
    again = (await client.get("/api/admin/settings", headers=ha)).json()
    assert again["registration_mode"] == "invite"
    assert again["signups_enabled"] is False
    assert again["default_monthly_token_limit"] == 12345
    assert again["branding"]["app_name"] == "Acme Docs"

    # Partial write keeps prior branding fields (only accent changes here).
    partial = await client.put(
        "/api/admin/settings",
        json={"branding": {"accent_color": "#FFFFFF"}},
        headers=ha,
    )
    assert partial.status_code == 200
    pb = partial.json()["branding"]
    assert pb["accent_color"] == "#FFFFFF"
    assert pb["app_name"] == "Acme Docs"
    assert pb["logo_url"] == "/static/logo.svg"


async def test_settings_branding_validation(client: AsyncClient) -> None:
    admin_token = await _admin_token(client)
    ha = {"Authorization": f"Bearer {admin_token}"}

    # Bad accent colors (not an allow-listed hex / HSL triple) -> 422. The accent
    # allow-list mirrors the client's normalizeAccent EXACTLY, so anything that
    # could break out of the CSSOM custom-property value is rejected.
    for bad in ("red", "#FF", "#12345", "rgb(1,2,3)", "url(x)", "0 0% 0%; color:red"):
        resp = await client.put(
            "/api/admin/settings",
            json={"branding": {"accent_color": bad}},
            headers=ha,
        )
        assert resp.status_code == 422, bad

    # Allow-listed accents accepted: 3- and 6-digit hex, and an HSL channel triple.
    for ok in ("#FFF", "#0A0B0C", "221 83% 53%"):
        resp = await client.put(
            "/api/admin/settings",
            json={"branding": {"accent_color": ok}},
            headers=ha,
        )
        assert resp.status_code == 200, ok
        assert resp.json()["branding"]["accent_color"] == ok

    # External / absolute logo_url -> 422 (CSP / mixed-content guard).
    for bad_logo in ("https://evil.example.com/logo.png", "//cdn.example.com/x.svg", "logo.svg"):
        resp = await client.put(
            "/api/admin/settings",
            json={"branding": {"logo_url": bad_logo}},
            headers=ha,
        )
        assert resp.status_code == 422, bad_logo

    # Invalid registration_mode -> 422.
    bad_mode = await client.put(
        "/api/admin/settings",
        json={"registration_mode": "bogus"},
        headers=ha,
    )
    assert bad_mode.status_code == 422


async def test_config_exposes_branding(client: AsyncClient) -> None:
    admin_token = await _admin_token(client)
    ha = {"Authorization": f"Bearer {admin_token}"}
    await client.put(
        "/api/admin/settings",
        json={"branding": {"app_name": "Branded", "accent_color": "#0A0B0C"}},
        headers=ha,
    )
    cfg = await client.get("/api/config")
    assert cfg.status_code == 200
    branding = cfg.json()["branding"]
    assert branding["app_name"] == "Branded"
    assert branding["accent_color"] == "#0A0B0C"
    # The private monthly-limit key never leaks into public branding.
    assert "_default_monthly_token_limit" not in branding


async def test_invites_lifecycle(client: AsyncClient) -> None:
    admin_token = await _admin_token(client)
    ha = {"Authorization": f"Bearer {admin_token}"}
    created = await client.post("/api/admin/invites", json={"role": "user"}, headers=ha)
    assert created.status_code == 200
    body = created.json()
    assert body["token"]  # token shown once
    invite_id = body["id"]

    listed = await client.get("/api/admin/invites", headers=ha)
    # The list NEVER carries the raw token.
    assert body["token"] not in listed.text
    assert any(i["id"] == invite_id for i in listed.json())

    deleted = await client.delete(f"/api/admin/invites/{invite_id}", headers=ha)
    assert deleted.status_code == 204
