"""Projects CRUD — fully tenant-scoped via :class:`TenantScope` (section 6).

Every handler reads/writes through the injected ``TenantScope``; none touches
the raw ORM/session. ``owner_id`` is taken from the authenticated user, never
the request body.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import TenantScopeDep
from app.api.errors import api_error
from app.api.schemas import ProjectCreate, ProjectPublic, ProjectUpdate
from app.models.project import Project

router = APIRouter()


@router.get("", response_model=list[ProjectPublic])
async def list_projects(scope: TenantScopeDep) -> list[ProjectPublic]:
    """List the current tenant's projects (newest first)."""
    projects = await scope.list(Project, order_by=Project.created_at.desc())
    return [ProjectPublic.model_validate(p) for p in projects]


@router.post("", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, scope: TenantScopeDep) -> ProjectPublic:
    """Create a project owned by the current tenant.

    Embedding pin columns stay NULL in Phase 1; the Phase-2 provider slice
    populates them at creation (default operator Gemini).
    """
    project = Project(
        owner_id=scope.user_id,
        name=payload.name,
        description=payload.description,
    )
    await scope.add(project)
    return ProjectPublic.model_validate(project)


@router.get("/{project_id}", response_model=ProjectPublic)
async def get_project(project_id: uuid.UUID, scope: TenantScopeDep) -> ProjectPublic:
    """Fetch one owned project. 404 if missing OR owned by another tenant."""
    project = await scope.get(Project, project_id)
    if project is None:
        raise api_error(404, "not_found", "Project not found.")
    return ProjectPublic.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectPublic)
async def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate, scope: TenantScopeDep
) -> ProjectPublic:
    """Update name/description of an owned project (partial)."""
    project = await scope.get(Project, project_id)
    if project is None:
        raise api_error(404, "not_found", "Project not found.")
    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    await scope.session.flush()
    return ProjectPublic.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: uuid.UUID, scope: TenantScopeDep) -> Response:
    """Delete an owned project. 404 if missing or not owned."""
    deleted = await scope.delete(Project, project_id)
    if not deleted:
        raise api_error(404, "not_found", "Project not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
