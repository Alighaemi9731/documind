"""Phase 1: auth + tenancy schema, enums, and RLS policies.

Creates the Phase-1 tables (users, auth_identities, projects, refresh_tokens,
invites, system_settings), the canonical PG enum types, required extensions,
and Row-Level-Security policies (ENABLE + FORCE) on the owner-scoped tables.

RLS policy (per ADR-0002): a row is visible/writable only when
``owner_id = current_setting('app.current_user_id', true)::uuid`` OR the admin
bypass GUC ``current_setting('app.is_admin', true) = 'true'`` is set. The admin
bypass exists for metadata tables only and is deliberately NOT extended to any
future document/chunk *content* table.

``users`` is RLS-scoped on its own ``id`` (a user may read/update their own
row). The auth service reads ``users`` on a non-RLS admin session for login,
which is correct because login predates a tenant identity.

Revision ID: 0001_phase1_auth_tenancy
Revises:
Create Date: 2026-06-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_phase1_auth_tenancy"
down_revision = None
branch_labels = None
depends_on = None


# Owner-scoped tables that get the standard owner_id RLS policy.
_OWNER_SCOPED_TABLES = ("projects",)


def _create_enum_types() -> None:
    op.execute("CREATE TYPE user_role AS ENUM ('user', 'admin')")
    op.execute("CREATE TYPE user_status AS ENUM ('active', 'pending', 'disabled')")
    op.execute("CREATE TYPE registration_mode AS ENUM ('open', 'approval', 'invite')")


def _drop_enum_types() -> None:
    op.execute("DROP TYPE IF EXISTS registration_mode")
    op.execute("DROP TYPE IF EXISTS user_status")
    op.execute("DROP TYPE IF EXISTS user_role")


def upgrade() -> None:
    # Extensions (idempotent; also seeded by deploy/postgres/init in prod).
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    _create_enum_types()

    user_role = postgresql.ENUM("user", "admin", name="user_role", create_type=False)
    user_status = postgresql.ENUM(
        "active", "pending", "disabled", name="user_status", create_type=False
    )
    registration_mode = postgresql.ENUM(
        "open", "approval", "invite", name="registration_mode", create_type=False
    )

    # ------------------------------------------------------------------ users
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="user"),
        sa.Column("status", user_status, nullable=False, server_default="active"),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("registration_source", sa.String(length=64), nullable=True),
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
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # -------------------------------------------------------- auth_identities
    op.create_table(
        "auth_identities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subject", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
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
        sa.UniqueConstraint("provider", "provider_subject", name="uq_identity_provider_subject"),
    )
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])

    # --------------------------------------------------------------- projects
    op.create_table(
        "projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("embedding_provider", sa.String(length=32), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column("embedding_normalized", sa.Boolean(), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])

    # --------------------------------------------------------- refresh_tokens
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_refresh_tokens_token_hash",
        "refresh_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])

    # ---------------------------------------------------------------- invites
    op.create_table(
        "invites",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("role", user_role, nullable=False, server_default="user"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["consumed_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_invites_token_hash", "invites", ["token_hash"], unique=True)

    # -------------------------------------------------------- system_settings
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "registration_mode",
            registration_mode,
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "default_provider",
            sa.String(length=32),
            nullable=False,
            server_default="google",
        ),
        sa.Column(
            "signups_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "branding",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.CheckConstraint("id = 1", name="ck_system_settings_singleton"),
    )

    _apply_rls()


def _apply_rls() -> None:
    """Enable + FORCE RLS.

    The admin bypass (``app.is_admin='true'``) is granted ONLY on the ``users``
    metadata table. Tenant *content* tables (``projects``, and the Phase-2
    ``documents``/``chunks``) get owner_id isolation with **no admin bypass**,
    so a mis-set GUC can never leak content across tenants (ADR-0002).

    ``NULLIF(..., '')`` guards the uuid cast against an empty GUC string: unset
    -> NULL -> matches no rows, rather than raising an invalid-uuid error.
    """
    # users: a user may see/modify only their own row; admins bypass (metadata).
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY users_self_isolation ON users
            USING (
                id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                OR current_setting('app.is_admin', true) = 'true'
            )
            WITH CHECK (
                id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                OR current_setting('app.is_admin', true) = 'true'
            )
        """)

    # owner_id-scoped tenant CONTENT tables: strict owner isolation, NO bypass.
    for table in _OWNER_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_owner_isolation ON {table}
                USING (
                    owner_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                )
                WITH CHECK (
                    owner_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                )
            """)


def downgrade() -> None:
    for table in _OWNER_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_owner_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS users_self_isolation ON users")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

    op.drop_table("system_settings")
    op.drop_index("ix_invites_token_hash", table_name="invites")
    op.drop_table("invites")
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_auth_identities_user_id", table_name="auth_identities")
    op.drop_table("auth_identities")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    _drop_enum_types()
