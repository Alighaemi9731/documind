"""Phase 4: BYOK keys, provider selections, usage + quota (ADR-0006/0009).

Creates five owner-scoped tenant tables — ``provider_keys``,
``provider_selections``, ``usage_events``, ``user_monthly_usage``,
``user_quota`` — each with ENABLE + FORCE RLS, owner-only (``user_id``) policies,
and **NO admin bypass** (ADR-0002): these hold a user's secrets and usage, which
a mis-set ``app.is_admin`` GUC must never leak across tenants. The Provider /
Capability / KeySource enums already exist as shared Python enums; the columns
store their string values directly (no PG enum type needed). ``NULLIF(...,'')``
guards the uuid cast against an empty GUC. Index ``usage_events(user_id,
created_at)`` for the admin time-series.

Revision ID: 0004_phase4_byok_quota
Revises: 0003_phase3_rag
Create Date: 2026-06-20
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_phase4_byok_quota"
down_revision = "0003_phase3_rag"
branch_labels = None
depends_on = None

# Tenant tables: owner-only (user_id) isolation, NO admin bypass (ADR-0002).
_USER_SCOPED_TABLES = (
    "provider_keys",
    "provider_selections",
    "usage_events",
    "user_monthly_usage",
    "user_quota",
)


def upgrade() -> None:
    # ------------------------------------------------------- provider_keys
    op.create_table(
        "provider_keys",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("key_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "capabilities",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "provider", name="uq_provider_keys_user_provider"),
    )
    op.create_index("ix_provider_keys_user_id", "provider_keys", ["user_id"])

    # --------------------------------------------------- provider_selections
    op.create_table(
        "provider_selections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "capability", name="uq_provider_selections_user_capability"),
    )
    op.create_index("ix_provider_selections_user_id", "provider_selections", ["user_id"])

    # ---------------------------------------------------------- usage_events
    op.create_table(
        "usage_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("key_source", sa.String(length=16), nullable=False),
        sa.Column("capability", sa.String(length=16), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_usage_events_user_created", "usage_events", ["user_id", "created_at"])

    # ------------------------------------------------------ user_monthly_usage
    op.create_table(
        "user_monthly_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "period", name="uq_user_monthly_usage_user_period"),
    )

    # ------------------------------------------------------------ user_quota
    op.create_table(
        "user_quota",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("monthly_token_limit", sa.BigInteger(), nullable=True),
        sa.Column("requests_per_day", sa.Integer(), nullable=True),
        sa.Column("hard_disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    # Install-wide shared-key usage counter (one row per period). NOT user-scoped
    # and intentionally NOT RLS-protected — it is the global ceiling backstop
    # across ALL users on the shared operator key (ADR-0009).
    op.create_table(
        "install_usage",
        sa.Column("period", sa.String(length=7), primary_key=True),
        sa.Column("tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    _apply_rls()


def _apply_rls() -> None:
    """ENABLE + FORCE RLS, owner-only (``user_id``) policies.

    These are per-user METADATA tables (encrypted keys, provider selections,
    usage, quota) — NOT document/chunk/message *content*. Per ADR-0002 the admin
    bypass is allow-listed to metadata/usage/keys-metadata, so admin oversight
    endpoints (which read these via ``admin_session``) include the
    ``app.is_admin`` bypass here; the encrypted key material is never returned by
    any endpoint (fingerprints only). For a normal user the request path runs
    with ``is_admin=false`` so the policy is strictly owner-only.
    ``NULLIF(...,'')`` makes an unset GUC match no rows.
    """
    for table in _USER_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_owner_isolation ON {table}
                USING (
                    user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                    OR current_setting('app.is_admin', true) = 'true'
                )
                WITH CHECK (
                    user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                    OR current_setting('app.is_admin', true) = 'true'
                )
            """)


def downgrade() -> None:
    for table in _USER_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_owner_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table("install_usage")
    op.drop_table("user_quota")
    op.drop_table("user_monthly_usage")
    op.drop_index("ix_usage_events_user_created", table_name="usage_events")
    op.drop_table("usage_events")
    op.drop_index("ix_provider_selections_user_id", table_name="provider_selections")
    op.drop_table("provider_selections")
    op.drop_index("ix_provider_keys_user_id", table_name="provider_keys")
    op.drop_table("provider_keys")
