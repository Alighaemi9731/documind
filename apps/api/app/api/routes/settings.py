"""User settings — BYOK keys + per-capability provider selection (section 6).

All endpoints are Bearer + self-scoped (the tenant id comes from the JWT, never
the body). Secrets NEVER leave the server: keys are write-only on POST and the
GET surfaces only ``{provider, fingerprint, valid, checked_at}``. Validation runs
ONE injectable health check per save (cached); the stored verdict drives
``is_active``. Selecting an unsupported ``(provider, capability)`` pair is 409
``capability_unsupported``; selecting an embedding provider whose dim differs
from an existing project pin (without re-embed) is 409 ``embedding_dim_mismatch``
(ADR-0015).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, TenantSession, client_ip
from app.api.errors import api_error
from app.api.schemas import (
    KeyCreateRequest,
    KeyCreateResponse,
    KeyMetadataPublic,
    ModelOption,
    ProviderInfo,
    ProvidersResponse,
    SelectionPublic,
    SelectionRequest,
)
from app.models.enums import Capability
from app.models.project import Project
from app.models.provider_selection import ProviderSelection
from app.providers import registry
from app.providers.keystore import crypto, validation
from app.providers.keystore import store as keystore
from app.providers.spec import ModelSpec
from app.services.rate_limit import RateLimiter

router = APIRouter()

# Saving a BYOK key triggers ONE outbound provider validation call; rate-limit
# per user + IP so it cannot be abused to burn outbound requests or the user's
# own key by POSTing many distinct keys (ARCHITECTURE.md section 9).
_key_save_limiter = RateLimiter(max_attempts=10, window_seconds=300.0)


@router.get("/keys", response_model=list[KeyMetadataPublic])
async def list_keys(user: CurrentUser, session: TenantSession) -> list[KeyMetadataPublic]:
    """List the user's stored keys as metadata only (NEVER the secret)."""
    meta = await keystore.list_user_keys(session, user_id=user.id)
    return [
        KeyMetadataPublic(
            provider=m.provider,
            fingerprint=m.fingerprint,
            valid=m.valid,
            checked_at=m.checked_at,
        )
        for m in meta
    ]


@router.post("/keys", response_model=KeyCreateResponse)
async def create_key(
    payload: KeyCreateRequest, user: CurrentUser, session: TenantSession, request: Request
) -> KeyCreateResponse:
    """Validate + store a BYOK key (write-only). Returns fingerprint + validity.

    Validation is ONE health check (debounced/cached + rate-limited per user/IP);
    a transient failure is treated as not-yet-valid but the key is still stored so
    the user can retry. The plaintext is never echoed back.
    """
    if not _key_save_limiter.allow(f"keysave:{user.id}:{client_ip(request)}"):
        raise api_error(429, "rate_limited", "Too many key updates; please slow down.")

    try:
        registry.get_spec(payload.provider)
    except KeyError as exc:
        raise api_error(422, "unknown_provider", "Unknown provider.", field="provider") from exc

    fingerprint = crypto.fingerprint(payload.api_key)
    result = validation.validate_key(payload.provider, payload.api_key, fingerprint=fingerprint)

    row = await keystore.save_user_key(
        session, user_id=user.id, provider=payload.provider, raw_key=payload.api_key
    )
    # The stored row's validity reflects the health check.
    row.is_active = result.valid
    await session.flush()

    return KeyCreateResponse(
        provider=payload.provider, fingerprint=row.key_fingerprint, valid=result.valid
    )


@router.delete("/keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(provider: str, user: CurrentUser, session: TenantSession) -> Response:
    """Delete the user's key for ``provider``. 204 even if absent (idempotent)."""
    await keystore.delete_user_key(session, user_id=user.id, provider=provider)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _model_option(spec_model: ModelSpec | None) -> ModelOption | None:
    if spec_model is None:
        return None
    return ModelOption(
        model=spec_model.model,
        dim=spec_model.dim,
        normalized=spec_model.normalized,
        max_input_tokens=spec_model.max_input_tokens,
    )


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers(user: CurrentUser, session: TenantSession) -> ProvidersResponse:
    """Available providers + capabilities + the user's current selections.

    No secrets — only which providers the user has a BYOK key for (``has_byok``).
    """
    keys = await keystore.list_user_keys(session, user_id=user.id)
    byok_providers = {k.provider for k in keys if k.valid}

    providers: list[ProviderInfo] = []
    for spec in registry.list_specs():
        providers.append(
            ProviderInfo(
                id=spec.id,
                label=spec.label,
                capabilities=[c.value for c in spec.capabilities],
                requires_byok=spec.requires_byok,
                chat=_model_option(spec.chat),
                embedding=_model_option(spec.embedding),
                key_format_hint=spec.extra.get("key_format_hint"),
                has_byok=spec.id in byok_providers,
            )
        )

    sel_result = await session.execute(
        select(ProviderSelection).where(ProviderSelection.user_id == user.id)
    )
    selections = [
        SelectionPublic(capability=s.capability, provider=s.provider, model=s.model)
        for s in sel_result.scalars().all()
    ]
    return ProvidersResponse(providers=providers, selections=selections)


@router.put("/providers", response_model=SelectionPublic)
async def set_provider(
    payload: SelectionRequest, user: CurrentUser, session: TenantSession
) -> SelectionPublic:
    """Set the user's provider+model for a capability.

    409 ``capability_unsupported`` if the provider doesn't offer the capability;
    409 ``embedding_dim_mismatch`` if switching the embedding provider to a model
    whose dim differs from an existing project pin (re-embed required, ADR-0015).
    """
    try:
        spec = registry.assert_supports(payload.provider, payload.capability)
    except registry.CapabilityUnsupported as exc:
        raise api_error(409, "capability_unsupported", str(exc)) from exc

    # Resolve + validate the chosen model belongs to the capability.
    if payload.capability is Capability.embedding:
        model_spec = spec.embedding
        if model_spec is None or payload.model != model_spec.model:
            raise api_error(409, "capability_unsupported", "Model not offered for embedding.")
        await _guard_embedding_dim(session, user_id=user.id, new_dim=model_spec.dim)
    else:
        model_spec = spec.chat
        if model_spec is None or payload.model != model_spec.model:
            raise api_error(409, "capability_unsupported", "Model not offered for chat.")

    result = await session.execute(
        select(ProviderSelection).where(
            ProviderSelection.user_id == user.id,
            ProviderSelection.capability == payload.capability.value,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = ProviderSelection(
            user_id=user.id,
            capability=payload.capability.value,
            provider=payload.provider,
            model=payload.model,
        )
        session.add(row)
    else:
        row.provider = payload.provider
        row.model = payload.model
    await session.flush()
    return SelectionPublic(
        capability=payload.capability.value, provider=payload.provider, model=payload.model
    )


async def _guard_embedding_dim(session, *, user_id, new_dim: int) -> None:  # noqa: ANN001
    """Block an in-place embedding switch to a different dim (ADR-0015).

    Any existing project pinned to a different dim must be re-embedded first;
    the in-place selection change is rejected with 409 ``embedding_dim_mismatch``.
    """
    result = await session.execute(
        select(Project.embedding_dim)
        .where(Project.owner_id == user_id, Project.embedding_dim.is_not(None))
        .distinct()
    )
    existing_dims = {d for (d,) in result.all() if d is not None}
    if existing_dims and any(d != new_dim for d in existing_dims):
        raise api_error(
            409,
            "embedding_dim_mismatch",
            "Embedding dimension differs from an existing project pin; re-embed first.",
        )


__all__ = ["router"]
