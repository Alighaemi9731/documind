"""Access to the ``system_settings`` singleton (registration mode, etc.).

The row is seeded from env on first run (installer / lifespan); this service
reads it and falls back to the env default if the row is absent, so the API
never crashes on a fresh DB.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.models.enums import RegistrationMode
from app.models.system_settings import SINGLETON_ID, SystemSettings


def _env_registration_mode() -> RegistrationMode:
    try:
        return RegistrationMode(app_settings.registration_mode)
    except ValueError:
        return RegistrationMode.open


async def get_system_settings(session: AsyncSession) -> SystemSettings | None:
    """Return the singleton settings row, or None if not yet seeded."""
    result = await session.execute(select(SystemSettings).where(SystemSettings.id == SINGLETON_ID))
    return result.scalar_one_or_none()


async def get_registration_mode(session: AsyncSession) -> RegistrationMode:
    """Effective registration mode: DB row if present, else env default."""
    row = await get_system_settings(session)
    if row is None:
        return _env_registration_mode()
    return row.registration_mode


async def ensure_system_settings(session: AsyncSession) -> SystemSettings:
    """Idempotently create the singleton row seeded from env defaults."""
    row = await get_system_settings(session)
    if row is not None:
        return row
    row = SystemSettings(
        id=SINGLETON_ID,
        registration_mode=_env_registration_mode(),
        default_provider=app_settings.default_provider,
        signups_enabled=True,
        branding={},
    )
    session.add(row)
    await session.flush()
    return row


__all__ = [
    "get_system_settings",
    "get_registration_mode",
    "ensure_system_settings",
]
