"""Shared pytest configuration.

Sets a test environment + a strong JWT secret *before* the app settings are
imported, so unit tests can mint/verify tokens without a real deployment and
``validate_secrets`` is a no-op in the ``test`` environment.
"""

from __future__ import annotations

import os

# Must be set before any ``app.core.config`` import.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-please-change-0123456789abcdef-0123456789")
os.environ.setdefault("PUBLIC_BASE_URL", "https://docs.example.com")
os.environ.setdefault("DOMAIN", "docs.example.com")
