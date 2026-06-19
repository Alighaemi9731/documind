"""Refresh + CSRF cookie helpers and the Origin/Referer allow-list check.

The refresh cookie is ``httpOnly; Secure; SameSite=Lax`` and Path-scoped to
``/api/auth`` so it is only ever attached to the refresh/logout endpoints
(ADR-0001). The CSRF cookie is readable by JS (double-submit) and shares the
same Path/SameSite. Origin/Referer of cookie POSTs must be on the allow-list.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request, Response

from app.core.config import settings

REFRESH_COOKIE_NAME = "documind_refresh"
CSRF_COOKIE_NAME = "documind_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
COOKIE_PATH = "/api/auth"


def _max_age_seconds() -> int:
    return settings.refresh_token_ttl_days * 24 * 60 * 60


def set_auth_cookies(response: Response, *, refresh_token: str, csrf_token: str) -> None:
    """Attach the refresh (httpOnly) + CSRF (readable) cookies to ``response``."""
    secure = settings.refresh_cookie_secure
    max_age = _max_age_seconds()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=COOKIE_PATH,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path=COOKIE_PATH,
    )


def clear_auth_cookies(response: Response) -> None:
    """Expire both cookies (logout)."""
    response.delete_cookie(REFRESH_COOKIE_NAME, path=COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE_NAME, path=COOKIE_PATH)


def origin_allowed(request: Request) -> bool:
    """Return True only if the request Origin/Referer is on the allow-list.

    Fails CLOSED: if neither header is present the request is rejected. A
    browser always sends Origin (or at least Referer) on a state-changing
    cross-origin POST; absence indicates a non-browser or forged request, which
    must not pass the CSRF gate (ADR-0001).
    """
    allowed = settings.allowed_origins()
    origin = request.headers.get("origin")
    if origin is not None:
        return origin.rstrip("/") in allowed
    referer = request.headers.get("referer")
    if referer is not None:
        parsed = urlparse(referer)
        ref_origin = f"{parsed.scheme}://{parsed.netloc}"
        return ref_origin in allowed
    return False


__all__ = [
    "REFRESH_COOKIE_NAME",
    "CSRF_COOKIE_NAME",
    "CSRF_HEADER_NAME",
    "COOKIE_PATH",
    "set_auth_cookies",
    "clear_auth_cookies",
    "origin_allowed",
]
