"""BYOK key validation — ONE cheap provider health check per explicit save.

A pasted key is validated by a single, cheap provider-side health check at save
time only (never per-keystroke): debounced + rate-limited per user/IP, and
cached with a TTL so the same key isn't re-validated within the window. Provider
base URLs are HARD-CODED in the ProviderSpec (never user-supplied), so there is
no SSRF surface.

The validator is INJECTABLE (:func:`set_validator`) so tests run with a stub and
make no network calls. The result is a generic shape (:class:`ValidationResult`)
— a valid/invalid/transient verdict only, never the provider's raw error body
(no oracle, no leak).
"""

from __future__ import annotations

import enum
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.providers import registry
from app.providers.errors import (
    ProviderAuthError,
    ProviderError,
    ProviderInvalidKeyError,
    ProviderTransientError,
)


class ValidationStatus(enum.StrEnum):
    """The generic outcome of a key health check (no provider detail)."""

    valid = "valid"
    invalid_key = "invalid_key"
    transient = "transient"


@dataclass(frozen=True)
class ValidationResult:
    """A generic validation verdict. Never carries a provider error body."""

    status: ValidationStatus

    @property
    def valid(self) -> bool:
        return self.status is ValidationStatus.valid


# A validator runs ONE provider health check given (provider_id, raw_key).
# It returns a ValidationResult and must never raise a provider error body to
# the caller. Injectable for tests via set_validator.
Validator = Callable[[str, str], ValidationResult]

# Cache TTL (seconds) for a (provider, fingerprint) verdict — avoids re-checking
# the same key on a rapid re-save.
CACHE_TTL_SECONDS = 300.0

_validator: Validator | None = None
# fingerprint-keyed cache: {(provider, fp): (expiry_monotonic, result)}
_cache: dict[tuple[str, str], tuple[float, ValidationResult]] = {}


def set_validator(validator: Validator | None) -> None:
    """Install (or clear) the process-wide validator. Tests inject a stub here."""
    global _validator
    _validator = validator


def clear_cache() -> None:
    """Drop the validation cache (test isolation / forced re-check)."""
    _cache.clear()


def _default_validator(provider_id: str, raw_key: str) -> ValidationResult:
    """Construct the adapter from the hard-coded spec and run one cheap call.

    Maps the normalized provider-error taxonomy to a generic verdict. The base
    URL comes from the ProviderSpec (hard-coded), never from user input.
    """
    try:
        spec = registry.get_spec(provider_id)
    except KeyError:
        return ValidationResult(ValidationStatus.invalid_key)

    try:
        adapter = registry.build_validation_probe(spec, raw_key)
        adapter()
    except (ProviderAuthError, ProviderInvalidKeyError):
        return ValidationResult(ValidationStatus.invalid_key)
    except ProviderTransientError:
        return ValidationResult(ValidationStatus.transient)
    except ProviderError:
        # Any other normalized provider failure: treat as invalid (no oracle).
        return ValidationResult(ValidationStatus.invalid_key)
    return ValidationResult(ValidationStatus.valid)


def validate_key(
    provider_id: str,
    raw_key: str,
    *,
    fingerprint: str,
    use_cache: bool = True,
) -> ValidationResult:
    """Validate a pasted key with ONE health check (cached by fingerprint).

    The cache key is ``(provider_id, fingerprint)`` — the fingerprint is a
    sha256 digest, so the raw key never enters the cache. A cached verdict
    within ``CACHE_TTL_SECONDS`` is returned without a new network call.
    """
    cache_key = (provider_id, fingerprint)
    now = time.monotonic()
    if use_cache:
        cached = _cache.get(cache_key)
        if cached is not None and cached[0] > now:
            return cached[1]

    validator = _validator or _default_validator
    result = validator(provider_id, raw_key)

    # Only cache definitive verdicts; a transient should be re-checked.
    if result.status is not ValidationStatus.transient:
        _cache[cache_key] = (now + CACHE_TTL_SECONDS, result)
    return result


__all__ = [
    "ValidationStatus",
    "ValidationResult",
    "Validator",
    "CACHE_TTL_SECONDS",
    "set_validator",
    "clear_cache",
    "validate_key",
]
