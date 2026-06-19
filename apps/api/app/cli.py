"""Admin CLI — ``python -m app.cli bootstrap-admin --email <addr>``.

``bootstrap-admin`` is an idempotent upsert: it ensures an account exists for
the given email, promotes it to admin, and marks it active. Re-running is a
no-op beyond reconciling role/status. It does NOT set a password — the admin
self-registers (which reconciles to admin) or an operator sets one later.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.core.db import admin_session, dispose_engine
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.services.auth_service import get_user_by_email, normalize_email
from app.services.settings_service import ensure_system_settings


async def _bootstrap_admin(email: str) -> str:
    """Idempotently upsert an admin user for ``email``; return a status word."""
    norm = normalize_email(email)
    async with admin_session() as session:
        await ensure_system_settings(session)
        user = await get_user_by_email(session, norm)
        if user is None:
            user = User(
                email=norm,
                role=UserRole.admin,
                status=UserStatus.active,
                registration_source="bootstrap",
            )
            session.add(user)
            await session.flush()
            return "created"

        changed = False
        if user.role is not UserRole.admin:
            user.role = UserRole.admin
            changed = True
        if user.status is not UserStatus.active:
            user.status = UserStatus.active
            changed = True
        await session.flush()
        return "reconciled" if changed else "unchanged"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="DocuMind admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    boot = sub.add_parser("bootstrap-admin", help="Idempotently upsert an admin user")
    boot.add_argument("--email", required=True, help="Admin account email")

    args = parser.parse_args(argv)

    if args.command == "bootstrap-admin":
        try:
            result = asyncio.run(_run_bootstrap(args.email))
        except Exception as exc:  # noqa: BLE001 - surface a clean CLI error
            print(f"bootstrap-admin failed: {exc}", file=sys.stderr)
            return 1
        print(f"bootstrap-admin: {result} ({args.email})")
        return 0

    parser.print_help()
    return 2


async def _run_bootstrap(email: str) -> str:
    try:
        return await _bootstrap_admin(email)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
