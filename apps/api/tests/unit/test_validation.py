"""BYOK key validation: valid / invalid / transient, ONE call per save, cached.

Uses an injected stub validator (no network). Asserts the generic verdict shape
(no provider error body), the per-fingerprint cache (one call within the TTL),
and that a transient result is NOT cached (re-checked)."""

from __future__ import annotations

import pytest

from app.providers.keystore import validation
from app.providers.keystore.validation import ValidationStatus


@pytest.fixture(autouse=True)
def _reset():
    validation.set_validator(None)
    validation.clear_cache()
    yield
    validation.set_validator(None)
    validation.clear_cache()


def test_valid_key() -> None:
    calls: list[tuple[str, str]] = []

    def _ok(provider: str, key: str) -> validation.ValidationResult:
        calls.append((provider, key))
        return validation.ValidationResult(ValidationStatus.valid)

    validation.set_validator(_ok)
    result = validation.validate_key("openai", "sk-x", fingerprint="fp1")
    assert result.valid
    assert len(calls) == 1


def test_invalid_key_no_oracle() -> None:
    validation.set_validator(lambda p, k: validation.ValidationResult(ValidationStatus.invalid_key))
    result = validation.validate_key("openai", "sk-bad", fingerprint="fp2")
    assert not result.valid
    assert result.status is ValidationStatus.invalid_key


def test_one_call_per_save_cached() -> None:
    calls: list[int] = []

    def _ok(provider: str, key: str) -> validation.ValidationResult:
        calls.append(1)
        return validation.ValidationResult(ValidationStatus.valid)

    validation.set_validator(_ok)
    # Same provider + fingerprint within the TTL: validator runs ONCE.
    validation.validate_key("openai", "sk-x", fingerprint="fpX")
    validation.validate_key("openai", "sk-x", fingerprint="fpX")
    validation.validate_key("openai", "sk-x", fingerprint="fpX")
    assert len(calls) == 1


def test_transient_not_cached() -> None:
    calls: list[int] = []

    def _transient(provider: str, key: str) -> validation.ValidationResult:
        calls.append(1)
        return validation.ValidationResult(ValidationStatus.transient)

    validation.set_validator(_transient)
    validation.validate_key("openai", "sk-x", fingerprint="fpT")
    validation.validate_key("openai", "sk-x", fingerprint="fpT")
    # Transient verdicts are re-checked (not cached).
    assert len(calls) == 2
