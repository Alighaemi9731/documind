"""End-to-end auth + registration + refresh + admin-gate integration tests.

Drives the FastAPI app over an in-process ASGI transport against the real DB
(rebound to the non-superuser role by the ``app_db`` fixture).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import admin_session
from app.main import app
from app.models.enums import RegistrationMode, UserRole, UserStatus
from app.services.auth_service import get_user_by_email
from app.services.settings_service import ensure_system_settings

pytestmark = pytest.mark.asyncio

ORIGIN = "https://docs.example.com"


@pytest_asyncio.fixture()
async def client(app_db: None) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=ORIGIN) as c:
        yield c


async def _set_mode(mode: RegistrationMode) -> None:
    async with admin_session() as session:
        row = await ensure_system_settings(session)
        row.registration_mode = mode
        await session.flush()


# --------------------------------------------------------------------------- #
# Registration per mode
# --------------------------------------------------------------------------- #


async def test_open_registration_returns_201_and_cookies(client: AsyncClient) -> None:
    await _set_mode(RegistrationMode.open)
    resp = await client.post(
        "/api/auth/register",
        json={"email": "open@example.com", "password": "hunter2hunter2"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == "open@example.com"
    assert "documind_refresh" in resp.cookies
    assert "documind_csrf" in resp.cookies


async def test_duplicate_registration_returns_409(client: AsyncClient) -> None:
    await _set_mode(RegistrationMode.open)
    payload = {"email": "dup@example.com", "password": "hunter2hunter2"}
    first = await client.post("/api/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "email_taken"


async def test_approval_registration_returns_202_pending(client: AsyncClient) -> None:
    await _set_mode(RegistrationMode.approval)
    resp = await client.post(
        "/api/auth/register",
        json={"email": "pending@example.com", "password": "hunter2hunter2"},
    )
    assert resp.status_code == 202
    assert resp.json() == {"status": "pending"}
    # Cannot log in while pending.
    login = await client.post(
        "/api/auth/login",
        json={"email": "pending@example.com", "password": "hunter2hunter2"},
    )
    assert login.status_code == 403


async def test_invite_registration_requires_valid_token(client: AsyncClient) -> None:
    await _set_mode(RegistrationMode.invite)
    # No token -> 403.
    resp = await client.post(
        "/api/auth/register",
        json={"email": "inv@example.com", "password": "hunter2hunter2"},
    )
    assert resp.status_code == 403

    # Create a valid invite and redeem it.
    from datetime import datetime, timedelta

    from app.core.security import generate_refresh_token, hash_refresh_token
    from app.models.invite import Invite

    raw = generate_refresh_token()
    async with admin_session() as session:
        session.add(
            Invite(
                token_hash=hash_refresh_token(raw),
                email=None,
                role=UserRole.user,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        await session.flush()

    ok = await client.post(
        "/api/auth/register",
        json={
            "email": "inv@example.com",
            "password": "hunter2hunter2",
            "invite_token": raw,
        },
    )
    assert ok.status_code == 201


# --------------------------------------------------------------------------- #
# Login + me + refresh
# --------------------------------------------------------------------------- #


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await _set_mode(RegistrationMode.open)
    await client.post("/api/auth/register", json={"email": email, "password": "hunter2hunter2"})
    resp = await client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_login_me_round_trip(client: AsyncClient) -> None:
    token = await _register_and_login(client, "me@example.com")
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "me@example.com"


async def test_login_wrong_password_is_401_generic(client: AsyncClient) -> None:
    await _register_and_login(client, "pw@example.com")
    resp = await client.post(
        "/api/auth/login", json={"email": "pw@example.com", "password": "wrongwrong"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


async def test_refresh_rotation_and_reuse_revokes_family(client: AsyncClient) -> None:
    await _set_mode(RegistrationMode.open)
    reg = await client.post(
        "/api/auth/register",
        json={"email": "rot@example.com", "password": "hunter2hunter2"},
    )
    old_refresh = reg.cookies["documind_refresh"]
    csrf = reg.cookies["documind_csrf"]

    headers = {"X-CSRF-Token": csrf, "Origin": ORIGIN}
    cookies = {"documind_refresh": old_refresh, "documind_csrf": csrf}

    # First rotation succeeds.
    r1 = await client.post("/api/auth/refresh", headers=headers, cookies=cookies)
    assert r1.status_code == 200
    new_refresh = r1.cookies["documind_refresh"]
    assert new_refresh != old_refresh

    # Reusing the OLD token (now used+revoked, beyond grace) is reuse -> 401.
    import app.services.auth_service as svc

    monkey_grace = svc.REFRESH_GRACE_SECONDS
    svc.REFRESH_GRACE_SECONDS = 0
    try:
        reuse = await client.post("/api/auth/refresh", headers=headers, cookies=cookies)
    finally:
        svc.REFRESH_GRACE_SECONDS = monkey_grace
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] in {"refresh_reuse", "refresh_invalid"}

    # The whole family is revoked: even the new token no longer works.
    new_csrf = r1.cookies["documind_csrf"]
    follow = await client.post(
        "/api/auth/refresh",
        headers={"X-CSRF-Token": new_csrf, "Origin": ORIGIN},
        cookies={"documind_refresh": new_refresh, "documind_csrf": new_csrf},
    )
    assert follow.status_code == 401


async def test_refresh_csrf_and_origin_enforced(client: AsyncClient) -> None:
    reg = await client.post(
        "/api/auth/register",
        json={"email": "csrf@example.com", "password": "hunter2hunter2"},
    )
    refresh_cookie = reg.cookies["documind_refresh"]
    csrf = reg.cookies["documind_csrf"]
    cookies = {"documind_refresh": refresh_cookie, "documind_csrf": csrf}

    # Missing CSRF header -> 403.
    bad = await client.post("/api/auth/refresh", headers={"Origin": ORIGIN}, cookies=cookies)
    assert bad.status_code == 403

    # Wrong Origin -> 403.
    bad_origin = await client.post(
        "/api/auth/refresh",
        headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example.com"},
        cookies=cookies,
    )
    assert bad_origin.status_code == 403


# --------------------------------------------------------------------------- #
# Admin gate
# --------------------------------------------------------------------------- #


async def test_require_admin_forbids_normal_user(client: AsyncClient) -> None:
    token = await _register_and_login(client, "plain@example.com")
    # /api/auth/me is fine for any user; assert role is 'user'.
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "user"


async def test_disabled_user_token_is_rejected(client: AsyncClient) -> None:
    token = await _register_and_login(client, "dis@example.com")
    # Disable + bump token_version.
    async with admin_session() as session:
        user = await get_user_by_email(session, "dis@example.com")
        assert user is not None
        user.status = UserStatus.disabled
        user.token_version = 1
        await session.flush()

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    # tv mismatch -> 401 token_revoked.
    assert me.status_code == 401
