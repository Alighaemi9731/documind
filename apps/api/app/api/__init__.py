from fastapi import APIRouter

from app.api.routes import (
    admin,
    auth,
    config,
    documents,
    health,
    projects,
    query,
    settings,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(
    documents.router,
    prefix="/projects/{project_id}/documents",
    tags=["documents"],
)
api_router.include_router(
    query.router,
    prefix="/projects/{project_id}/query",
    tags=["query"],
)
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
