"""Auth endpoints: register / login / refresh / logout / me (section 6).

Cookie POSTs (refresh, logout) enforce the double-submit CSRF token and an
Origin/Referer allow-list (ADR-0001). This router is the only place
``Set-Cookie`` is issued on the API side.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.api.cookies import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    REFRESH_COOKIE_NAME,
    clear_auth_cookies,
    origin_allowed,
    set_auth_cookies,
)
from app.api.deps import CurrentUser, client_ip
from app.api.errors import api_error
from app.api.schemas import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from app.core.config import settings
from app.core.db import admin_session
from app.core.security import (
    create_access_token,
    csrf_tokens_match,
    generate_csrf_token,
)
from app.models.user import User
from app.services import auth_service
from app.services.auth_service import AuthError, RegistrationPending
from app.services.rate_limit import login_email_limiter, login_limiter, register_limiter
from app.services.settings_service import get_registration_mode

router = APIRouter()


def _access_token_for(user: User) -> tuple[str, int]:
    ttl = settings.access_token_ttl_minutes * 60
    token = create_access_token(
        user_id=user.id,
        role=user.role.value,
        token_version=user.token_version,
        expires_in_seconds=ttl,
    )
    return token, ttl


async def _issue_session_cookies(
    response: Response,
    user: User,
    request: Request,
) -> None:
    """Mint a refresh-token family + CSRF token and attach both cookies."""
    csrf = generate_csrf_token()
    async with admin_session() as session:
        issued = await auth_service.issue_refresh_token(
            session,
            user_id=user.id,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    set_auth_cookies(response, refresh_token=issued.token, csrf_token=csrf)


@router.post("/register")
async def register(payload: RegisterRequest, request: Request) -> Response:
    """Create an account honoring REGISTRATION_MODE.

    open -> 201 + access token + refresh/csrf cookies;
    approval -> 202 {status:pending}; invite -> 201 or 403; dup -> 409.
    """
    if not register_limiter.allow(f"register:{client_ip(request)}"):
        raise api_error(429, "rate_limited", "Too many attempts. Try again later.")

    async with admin_session() as session:
        mode = await get_registration_mode(session)
        try:
            user = await auth_service.register(
                session,
                email=payload.email,
                password=payload.password,
                registration_mode=mode,
                invite_token=payload.invite_token,
                admin_email=settings.admin_email or None,
            )
        except RegistrationPending:
            return JSONResponse(status_code=202, content={"status": "pending"})
        except AuthError as exc:
            if exc.code == "email_taken":
                raise api_error(409, exc.code, exc.message) from exc
            if exc.code in {"invite_required", "invite_invalid"}:
                raise api_error(403, exc.code, exc.message) from exc
            raise api_error(400, exc.code, exc.message) from exc

    token, ttl = _access_token_for(user)
    body = TokenResponse(
        access_token=token,
        expires_in=ttl,
        user=UserPublic.model_validate(user),
    )
    response = JSONResponse(status_code=201, content=body.model_dump(mode="json"))
    await _issue_session_cookies(response, user, request)
    return response


@router.post("/login")
async def login(payload: LoginRequest, request: Request) -> Response:
    """Authenticate. 200 + tokens on success; 401 generic; 403 pending/disabled."""
    ip = client_ip(request)
    email_key = f"login-email:{auth_service.normalize_email(payload.email)}"
    if not login_limiter.allow(f"login:{ip}") or not login_email_limiter.allow(email_key):
        raise api_error(429, "rate_limited", "Too many attempts. Try again later.")

    async with admin_session() as session:
        try:
            user = await auth_service.authenticate(
                session, email=payload.email, password=payload.password
            )
        except AuthError as exc:
            if exc.code in {"account_pending", "account_disabled"}:
                raise api_error(403, exc.code, exc.message) from exc
            raise api_error(401, "invalid_credentials", "Invalid email or password.") from exc

    token, ttl = _access_token_for(user)
    body = TokenResponse(
        access_token=token,
        expires_in=ttl,
        user=UserPublic.model_validate(user),
    )
    response = JSONResponse(status_code=200, content=body.model_dump(mode="json"))
    await _issue_session_cookies(response, user, request)
    return response


def _require_csrf(request: Request) -> None:
    """Enforce Origin allow-list + double-submit CSRF on cookie POSTs."""
    if not origin_allowed(request):
        raise api_error(403, "bad_origin", "Origin not allowed.")
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not csrf_tokens_match(cookie_token, header_token):
        raise api_error(403, "csrf_failed", "CSRF validation failed.")


@router.post("/refresh")
async def refresh(request: Request) -> Response:
    """Rotate the refresh token. Reuse -> 401 + family revoke (ADR-0001)."""
    _require_csrf(request)
    raw = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw:
        raise api_error(401, "no_refresh", "Missing refresh token.")

    async with admin_session() as session:
        try:
            user, issued = await auth_service.rotate_refresh_token(
                session,
                raw_token=raw,
                ip=client_ip(request),
                user_agent=request.headers.get("user-agent"),
            )
        except AuthError as exc:
            response = JSONResponse(
                status_code=401,
                content={"error": {"code": exc.code, "message": exc.message}},
            )
            clear_auth_cookies(response)
            return response

    token, ttl = _access_token_for(user)
    csrf = generate_csrf_token()
    body = TokenResponse(
        access_token=token,
        expires_in=ttl,
        user=UserPublic.model_validate(user),
    )
    response = JSONResponse(status_code=200, content=body.model_dump(mode="json"))
    set_auth_cookies(response, refresh_token=issued.token, csrf_token=csrf)
    return response


@router.post("/logout", status_code=204)
async def logout(request: Request) -> Response:
    """Revoke the presented refresh token family. Always clears cookies (204)."""
    _require_csrf(request)
    raw = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw:
        async with admin_session() as session:
            await auth_service.revoke_refresh_token(session, raw_token=raw)
    response = Response(status_code=204)
    clear_auth_cookies(response)
    return response


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser) -> MeResponse:
    """Return the current user (provider/quota fields stubbed in Phase 1)."""
    return MeResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        status=user.status,
        active_provider=None,
        has_byok={},
        quota={"used": 0, "limit": None},
    )


__all__ = ["router"]
