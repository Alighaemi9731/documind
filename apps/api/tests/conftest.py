"""Shared pytest configuration.

Sets a test environment + a strong JWT secret *before* the app settings are
imported, so unit tests can mint/verify tokens without a real deployment and
``validate_secrets`` is a no-op in the ``test`` environment.
"""

from __future__ import annotations

import os
import tempfile

# Must be set before any ``app.core.config`` import.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-please-change-0123456789abcdef-0123456789")
os.environ.setdefault("PUBLIC_BASE_URL", "https://docs.example.com")
os.environ.setdefault("DOMAIN", "docs.example.com")
# Uploads land in a throwaway temp dir during tests (the prod default is the
# container path /data/uploads, which doesn't exist on a dev box).
os.environ.setdefault("UPLOADS_DIR", tempfile.mkdtemp(prefix="documind-test-uploads-"))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Rate limiters are process-global and keyed by client IP. In tests every
    request shares one IP, so reset them between tests to avoid cross-test 429s
    (in production each user has a distinct IP, so there is no accumulation)."""
    from app.services.rate_limit import login_email_limiter, login_limiter, register_limiter

    for limiter in (login_limiter, login_email_limiter, register_limiter):
        limiter._buckets.clear()
    yield
