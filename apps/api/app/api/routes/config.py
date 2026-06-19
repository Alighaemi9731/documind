"""Public ``GET /api/config`` — UI bootstrap values (ARCHITECTURE.md section 6).

No auth. Returns the upload cap (so the FileDropzone can validate client-side),
the effective registration mode (DB singleton if seeded, else env default), and
the branding payload (app name, accent color, optional same-origin logo path).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import BrandingPublic, ConfigResponse, branding_from_stored
from app.core.config import settings
from app.core.db import admin_session
from app.services.settings_service import get_registration_mode, get_system_settings

router = APIRouter()


@router.get("", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Return public UI config (upload cap + registration mode + branding)."""
    mode = settings.registration_mode
    branding = BrandingPublic()
    try:
        async with admin_session() as session:
            mode = (await get_registration_mode(session)).value
            row = await get_system_settings(session)
            branding = branding_from_stored(row.branding if row is not None else None)
    except Exception:  # noqa: BLE001 - DB may be unreachable; fall back to env/defaults.
        mode = settings.registration_mode
        branding = BrandingPublic()
    return ConfigResponse(
        max_upload_mb=settings.max_upload_mb,
        registration_mode=mode,
        branding=branding,
    )


__all__ = ["router"]
