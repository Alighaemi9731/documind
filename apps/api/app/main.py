import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import api_router
from app.core.config import settings
from app.core.db import dispose_engine, get_engine

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger("documind.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate secrets, create the hardened async engine, dispose on shutdown.

    ``settings.validate_secrets()`` fails fast on a weak/missing JWT secret in
    non-test environments. Engine creation is wrapped so the app still starts
    when DATABASE_URL is a placeholder/unreachable; readiness then reports
    not_ready.
    """
    settings.validate_secrets()

    engine = None
    try:
        engine = get_engine()
        logger.info("Database engine created")
    except Exception as exc:  # noqa: BLE001 - never block startup
        logger.warning("Could not create database engine: %s", exc)
        engine = None

    app.state.engine = engine

    # In-process ingest worker (ADR-0005). Started ONLY outside the test
    # environment — tests drive ingestion synchronously via process_one().
    worker_task: asyncio.Task[None] | None = None
    if engine is not None and settings.environment.lower() != "test":
        worker_task = asyncio.create_task(_run_ingest_worker())
        logger.info("Ingest worker started")

    app.state.worker_task = worker_task
    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await worker_task
        if engine is not None:
            await dispose_engine()
            logger.info("Database engine disposed")


async def _run_ingest_worker() -> None:
    """Run the bounded ingest loop.

    The embedder is resolved PER JOB (per owner: BYOK → shared operator) inside
    the worker, so the loop starts even when no operator default key is seeded
    (e.g. a BYOK-only install) instead of crashing at startup.
    """
    from app.ingestion.storage import read_document_bytes
    from app.ingestion.worker import run_forever

    await run_forever(read_bytes=read_document_bytes)


app = FastAPI(title="DocuMind API", version=__version__, lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Emit the canonical ``{error:{code,message,field?}}`` envelope (section 6).

    ``api_error`` already packs ``detail={"error": {...}}``; surface it at the
    top level. Any other HTTPException is wrapped into the same shape.
    """
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": str(detail)}},
    )


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Map request-body validation errors to a 422 in the canonical shape."""
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = [str(p) for p in first.get("loc", []) if p not in ("body", "query", "path")]
    error: dict[str, str] = {
        "code": "validation_error",
        "message": str(first.get("msg", "Invalid request.")),
    }
    if loc:
        error["field"] = ".".join(loc)
    return JSONResponse(status_code=422, content={"error": error})


app.include_router(api_router, prefix="/api")
