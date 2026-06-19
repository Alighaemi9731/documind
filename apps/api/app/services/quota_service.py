"""Atomic per-call quota reserve, enforced ONLY on the shared key (ADR-0009).

BYOK calls BYPASS quota entirely (the user pays their own provider). For shared
(operator-key) calls the seam is:

    reservation = await check_and_reserve(session, user, key_source)  # pre-call
    ... provider call ...
    await record_usage(session, ..., reservation, actual_tokens=...)   # reconcile

``check_and_reserve`` does an atomic ``INSERT ... ON CONFLICT DO UPDATE ...
RETURNING`` (no Redis in the base profile) on the per-user rolling counter row
for the current period, reserving an estimate up front. It rejects with
:class:`QuotaExceeded` (-> HTTP 429 + add-your-own-key message) when the reserve
would cross the per-user ``monthly_token_limit`` OR the GLOBAL per-install
ceiling on the shared key. After the call, :func:`record_usage` writes the
append-only :class:`UsageEvent` and reconciles the counter against the ACTUAL
tokens (refund/extra). ``key_source`` attribution is the single guard that shared
can never be mislabeled byok.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import Capability, KeySource
from app.models.usage import UsageEvent, UserQuota

# Conservative up-front reservation when the call's token cost is not yet known.
DEFAULT_RESERVE_TOKENS = 4096


class QuotaError(RuntimeError):
    """Base class for quota failures (typed for the route layer)."""


class QuotaExceeded(QuotaError):
    """The shared-key reservation would exceed the per-user or global limit (429)."""


class QuotaDisabled(QuotaError):
    """The user's shared-key access is hard-disabled by an admin (429/403)."""


@dataclass
class Reservation:
    """A pending shared-key reservation to reconcile after the provider call."""

    user_id: uuid.UUID
    period: str
    reserved: int
    key_source: KeySource


def current_period(now: datetime | None = None) -> str:
    """The rolling-window key for quota, e.g. ``2026-06``."""
    moment = now or datetime.now(UTC)
    return f"{moment.year:04d}-{moment.month:02d}"


async def _effective_limit(session: AsyncSession, user_id: uuid.UUID) -> tuple[int, bool]:
    """Return (per-user monthly token limit, hard_disabled) — install default if unset."""
    result = await session.execute(select(UserQuota).where(UserQuota.user_id == user_id))
    quota = result.scalar_one_or_none()
    if quota is None:
        return settings.default_monthly_token_limit, False
    limit = (
        quota.monthly_token_limit
        if quota.monthly_token_limit is not None
        else settings.default_monthly_token_limit
    )
    return limit, quota.hard_disabled


async def check_and_reserve(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    key_source: KeySource,
    estimate: int = DEFAULT_RESERVE_TOKENS,
    period: str | None = None,
) -> Reservation:
    """Atomic pre-call reserve. NO-OP for BYOK; enforced for shared (ADR-0009).

    Uses ``INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING`` so the read +
    increment of the rolling counter is a single atomic statement (row-locked by
    Postgres). Rejects with :class:`QuotaExceeded` when over the per-user limit or
    the global per-install ceiling, and :class:`QuotaDisabled` when hard-disabled.
    """
    if key_source is KeySource.byok:
        # BYOK bypasses quota; nothing is reserved or counted against the limit.
        return Reservation(
            user_id=user_id,
            period=period or current_period(),
            reserved=0,
            key_source=KeySource.byok,
        )

    period = period or current_period()
    limit, hard_disabled = await _effective_limit(session, user_id)
    if hard_disabled:
        raise QuotaDisabled("Shared-key access is disabled for this account.")

    # Atomic increment-and-return; if the new total exceeds the limit we roll it
    # back below (the increment is committed only if the reservation stands).
    result = await session.execute(
        text(
            """
            INSERT INTO user_monthly_usage (user_id, period, tokens, updated_at)
            VALUES (:uid, :period, :est, now())
            ON CONFLICT (user_id, period)
            DO UPDATE SET tokens = user_monthly_usage.tokens + :est, updated_at = now()
            RETURNING tokens
            """
        ),
        {"uid": str(user_id), "period": period, "est": estimate},
    )
    new_total = int(result.scalar_one())

    if new_total > limit:
        await _refund(session, "user_monthly_usage", estimate, user_id=user_id, period=period)
        raise QuotaExceeded(
            "Shared-key quota exceeded (your monthly limit). "
            "Add your own provider key in settings to continue."
        )

    # Install-wide ceiling: atomically increment the per-period install counter
    # and check the returned total across ALL users on the shared operator key.
    install_total = int(
        (
            await session.execute(
                text(
                    """
                    INSERT INTO install_usage (period, tokens, updated_at)
                    VALUES (:period, :est, now())
                    ON CONFLICT (period)
                    DO UPDATE SET tokens = install_usage.tokens + :est, updated_at = now()
                    RETURNING tokens
                    """
                ),
                {"period": period, "est": estimate},
            )
        ).scalar_one()
    )
    if install_total > settings.global_monthly_token_ceiling:
        # Roll back BOTH the install and per-user reservations and reject.
        await _refund(session, "install_usage", estimate, period=period)
        await _refund(session, "user_monthly_usage", estimate, user_id=user_id, period=period)
        raise QuotaExceeded(
            "Shared-key quota exceeded (global install limit). "
            "Add your own provider key in settings to continue."
        )

    return Reservation(
        user_id=user_id, period=period, reserved=estimate, key_source=KeySource.shared
    )


async def _refund(
    session: AsyncSession,
    table: str,
    amount: int,
    *,
    user_id: uuid.UUID | None = None,
    period: str,
) -> None:
    """Subtract ``amount`` from a usage counter (clamped at 0). ``table`` is a
    fixed internal literal (never user input)."""
    where = "period = :period" + (" AND user_id = :uid" if user_id is not None else "")
    params: dict[str, object] = {"amt": amount, "period": period}
    if user_id is not None:
        params["uid"] = str(user_id)
    await session.execute(
        text(f"UPDATE {table} SET tokens = GREATEST(tokens - :amt, 0) WHERE {where}"),
        params,
    )


async def record_usage(
    session: AsyncSession,
    *,
    reservation: Reservation,
    provider: str,
    capability: Capability,
    project_id: uuid.UUID | None,
    tokens_in: int,
    tokens_out: int,
) -> None:
    """Write the append-only UsageEvent and reconcile the reserve vs actual.

    For BYOK the counter is never touched (no reservation was made); the usage
    event is still recorded for analytics with ``key_source=byok``.
    """
    session.add(
        UsageEvent(
            user_id=reservation.user_id,
            project_id=project_id,
            provider=provider,
            key_source=reservation.key_source.value,
            capability=capability.value,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
    )

    if reservation.key_source is KeySource.byok:
        await session.flush()
        return

    actual = tokens_in + tokens_out
    delta = actual - reservation.reserved
    if delta != 0:
        await session.execute(
            text(
                "UPDATE user_monthly_usage SET tokens = GREATEST(tokens + :delta, 0), "
                "updated_at = now() WHERE user_id = :uid AND period = :period"
            ),
            {"delta": delta, "uid": str(reservation.user_id), "period": reservation.period},
        )
        # Keep the install-wide counter in sync with the same reconciliation.
        await session.execute(
            text(
                "UPDATE install_usage SET tokens = GREATEST(tokens + :delta, 0), "
                "updated_at = now() WHERE period = :period"
            ),
            {"delta": delta, "period": reservation.period},
        )
    await session.flush()


__all__ = [
    "DEFAULT_RESERVE_TOKENS",
    "QuotaError",
    "QuotaExceeded",
    "QuotaDisabled",
    "Reservation",
    "current_period",
    "check_and_reserve",
    "record_usage",
]
