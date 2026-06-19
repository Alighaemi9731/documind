from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter()


@router.get("/live")
async def live() -> dict[str, str]:
    """Liveness probe — no external dependencies."""
    return {"status": "ok", "service": "documind-api"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Readiness probe.

    Checks database connectivity and the presence of the 'vector'
    (pgvector) extension. Degrades gracefully: any failure yields a 503
    with a per-check breakdown rather than crashing.
    """
    checks: dict[str, Any] = {
        "database": False,
        "vector_extension": False,
    }

    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": checks},
        )

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            checks["database"] = True

            result = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            checks["vector_extension"] = result.scalar() is not None
    except Exception:
        # Never crash on a readiness check; report what we know.
        pass

    if all(checks.values()):
        return JSONResponse(
            status_code=200,
            content={"status": "ready", "checks": checks},
        )

    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "checks": checks},
    )
