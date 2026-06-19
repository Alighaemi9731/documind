"""Public ``GET /api/config`` — UI bootstrap values (ARCHITECTURE.md section 6).

No auth. Returns the upload cap (so the FileDropzone can validate client-side)
and the effective registration mode (DB singleton if seeded, else env default).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import ConfigResponse
from app.core.config import settings
from app.core.db import admin_session
from app.services.settings_service import get_registration_mode

router = APIRouter()


@router.get("", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Return public UI config."""
    mode = settings.registration_mode
    try:
        async with admin_session() as session:
            mode = (await get_registration_mode(session)).value
    except Exception:  # noqa: BLE001 - DB may be unreachable; fall back to env.
        mode = settings.registration_mode
    return ConfigResponse(max_upload_mb=settings.max_upload_mb, registration_mode=mode)


__all__ = ["router"]
