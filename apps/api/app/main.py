import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from app import __version__
from app.api import api_router
from app.core.config import settings

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger("documind.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the async SQLAlchemy engine on startup, dispose on shutdown.

    Engine creation is wrapped in try/except so the app still starts when
    the configured DATABASE_URL is a placeholder or unreachable. In that
    case app.state.engine is None and readiness checks report not_ready.
    """
    engine = None
    try:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        logger.info("Database engine created")
    except Exception as exc:  # noqa: BLE001 - never block startup
        logger.warning("Could not create database engine: %s", exc)
        engine = None

    app.state.engine = engine
    try:
        yield
    finally:
        if engine is not None:
            await engine.dispose()
            logger.info("Database engine disposed")


app = FastAPI(title="DocuMind API", version=__version__, lifespan=lifespan)

app.include_router(api_router, prefix="/api")
