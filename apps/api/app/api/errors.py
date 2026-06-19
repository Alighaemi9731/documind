"""Canonical API error shape: ``{error:{code,message,field?}}`` (section 6)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str, field: str | None = None) -> HTTPException:
    """Build an HTTPException whose detail follows the canonical error shape."""
    error: dict[str, Any] = {"code": code, "message": message}
    if field is not None:
        error["field"] = field
    return HTTPException(status_code=status_code, detail={"error": error})


__all__ = ["api_error"]
