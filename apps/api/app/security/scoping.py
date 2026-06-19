"""``TenantScope`` — the ONLY path that reads/writes tenant data (ADR-0002).

No route handler touches the raw ORM/session for tenant rows; everything goes
through a :class:`TenantScope` bound to the current user id. The scope clamps
every query to ``model.owner_id == user_id`` and re-asserts the connection GUC
before executing, so an app-layer mistake cannot bypass isolation and a missing
GUC fails loudly rather than leaking.
"""

from __future__ import annotations

import uuid
from typing import Any, TypeVar, cast

from sqlalchemy import CursorResult, Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Delete

from app.core.db import assert_guc

ModelT = TypeVar("ModelT")


def scope(query: Select[Any], model: Any, user_id: uuid.UUID) -> Select[Any]:
    """Clamp a SELECT to a single tenant: ``model.owner_id == user_id``.

    Canonical signature referenced by ARCHITECTURE.md section 6.
    """
    return query.where(model.owner_id == user_id)


class TenantScope:
    """Owner-scoped repository over a GUC-pinned session.

    Construct with the active session and the current user's id. Every helper
    re-asserts the GUC before touching the database.
    """

    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    @property
    def session(self) -> AsyncSession:
        return self._session

    @property
    def user_id(self) -> uuid.UUID:
        return self._user_id

    def select(self, model: type[ModelT]) -> Select[tuple[ModelT]]:
        """A SELECT already scoped to this tenant."""
        return scope(select(model), model, self._user_id)

    async def list(self, model: type[ModelT], *, order_by: Any | None = None) -> list[ModelT]:
        """Return all rows of ``model`` owned by this tenant."""
        await assert_guc(self._session, self._user_id)
        stmt = self.select(model)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, model: type[ModelT], entity_id: uuid.UUID) -> ModelT | None:
        """Return one owned row by id, or None if missing/not owned."""
        await assert_guc(self._session, self._user_id)
        stmt = scope(select(model), model, self._user_id).where(model.id == entity_id)  # type: ignore[attr-defined]
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, entity: ModelT) -> ModelT:
        """Persist a new owned entity. ``owner_id`` must already equal user_id.

        Raises if the caller tried to stamp a different owner (defence against
        an owner_id taken from the request body).
        """
        await assert_guc(self._session, self._user_id)
        owner = getattr(entity, "owner_id", None)
        if owner is not None and owner != self._user_id:
            raise PermissionError("Refusing to insert a row owned by another user.")
        if owner is None and hasattr(entity, "owner_id"):
            entity.owner_id = self._user_id
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def delete(self, model: type[ModelT], entity_id: uuid.UUID) -> bool:
        """Delete one owned row by id. Returns True if a row was removed."""
        await assert_guc(self._session, self._user_id)
        stmt: Delete = (
            delete(model)
            .where(model.owner_id == self._user_id)  # type: ignore[attr-defined]
            .where(model.id == entity_id)  # type: ignore[attr-defined]
        )
        result = cast(CursorResult[Any], await self._session.execute(stmt))
        return bool(result.rowcount)


__all__ = ["TenantScope", "scope"]
