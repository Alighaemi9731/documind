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

from sqlalchemy import text

from app.core.config import settings
from app.core.db import admin_session, dispose_engine, get_sessionmaker
from app.models.enums import Provider, UserRole, UserStatus
from app.models.user import User
from app.providers.keystore import crypto
from app.providers.keystore.operator_default import seed_operator_default
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


async def _seed_operator_key(key: str | None) -> str:
    """Seed the operator-default Gemini key from arg or env (idempotent)."""
    raw = key or settings.operator_default_gemini_key
    if not raw:
        raise RuntimeError("No key provided (pass --key or set OPERATOR_DEFAULT_GEMINI_KEY).")
    async with admin_session() as session:
        row = await seed_operator_default(session, raw, provider=Provider.google.value)
    return f"seeded {row.provider} (version {row.key_version}, {row.key_fingerprint})"


async def _rotate_master_key() -> str:
    """Re-encrypt dormant provider_keys + operator_default under the CURRENT key.

    MASTER_KEY_FERNET must list the NEW (current) key first and retain the old
    key(s) for decryption. Each ciphertext is decrypted with any configured key
    and re-encrypted with the current one (MultiFernet rotation), so an old key
    can be safely retired afterward. Runs as the DB owner/superuser (RLS FORCE on
    provider_keys has no admin bypass; the maintenance role must own/bypass).
    """
    maker = get_sessionmaker()
    rotated_keys = 0
    rotated_ops = 0
    async with maker() as session, session.begin():
        rows = (await session.execute(text("SELECT id, ciphertext FROM provider_keys"))).all()
        for row_id, ciphertext in rows:
            new_ct = crypto.rotate_ciphertext(bytes(ciphertext))
            await session.execute(
                text("UPDATE provider_keys SET ciphertext = :ct WHERE id = :id"),
                {"ct": new_ct, "id": row_id},
            )
            rotated_keys += 1

        op_rows = (await session.execute(text("SELECT id, ciphertext FROM operator_default"))).all()
        for row_id, ciphertext in op_rows:
            new_ct = crypto.rotate_ciphertext(bytes(ciphertext))
            await session.execute(
                text("UPDATE operator_default SET ciphertext = :ct WHERE id = :id"),
                {"ct": new_ct, "id": row_id},
            )
            rotated_ops += 1

    return f"re-encrypted {rotated_keys} provider key(s) and {rotated_ops} operator key(s)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="DocuMind admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    boot = sub.add_parser("bootstrap-admin", help="Idempotently upsert an admin user")
    boot.add_argument("--email", required=True, help="Admin account email")

    seed = sub.add_parser("seed-operator-key", help="Seed/rotate the operator Gemini key")
    seed.add_argument(
        "--key", required=False, help="Key (defaults to env OPERATOR_DEFAULT_GEMINI_KEY)"
    )

    sub.add_parser(
        "rotate-master-key",
        help="Re-encrypt dormant keys under the new MASTER_KEY_FERNET (current key first)",
    )

    args = parser.parse_args(argv)

    if args.command == "bootstrap-admin":
        try:
            result = asyncio.run(_run_bootstrap(args.email))
        except Exception as exc:  # noqa: BLE001 - surface a clean CLI error
            print(f"bootstrap-admin failed: {exc}", file=sys.stderr)
            return 1
        print(f"bootstrap-admin: {result} ({args.email})")
        return 0

    if args.command == "seed-operator-key":
        try:
            result = asyncio.run(_run_seed(args.key))
        except Exception as exc:  # noqa: BLE001 - surface a clean CLI error
            print(f"seed-operator-key failed: {exc}", file=sys.stderr)
            return 1
        print(f"seed-operator-key: {result}")
        return 0

    if args.command == "rotate-master-key":
        try:
            result = asyncio.run(_run_rotate())
        except Exception as exc:  # noqa: BLE001 - surface a clean CLI error
            print(f"rotate-master-key failed: {exc}", file=sys.stderr)
            return 1
        print(f"rotate-master-key: {result}")
        return 0

    parser.print_help()
    return 2


async def _run_bootstrap(email: str) -> str:
    try:
        return await _bootstrap_admin(email)
    finally:
        await dispose_engine()


async def _run_seed(key: str | None) -> str:
    try:
        return await _seed_operator_key(key)
    finally:
        await dispose_engine()


async def _run_rotate() -> str:
    try:
        return await _rotate_master_key()
    finally:
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
