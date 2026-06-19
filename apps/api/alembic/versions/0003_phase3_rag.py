"""Phase 3: RAG core — conversations + messages (chat persistence, ADR-0017).

Creates the ``message_role`` PG enum and the ``conversations`` / ``messages``
tables. Both are tenant CONTENT tables: ENABLE + FORCE RLS with **owner-only**
policies (``owner_id = NULLIF(current_setting('app.current_user_id', true),'')::uuid``)
and NO admin bypass (ADR-0002). ``messages`` persists the validated Citation[]
(JSONB) and the authoritative ``grounded`` flag with the assistant turn so the
SSE ``done`` event's ``message_id`` is durable.

Revision ID: 0003_phase3_rag
Revises: 0002_phase2_ingestion
Create Date: 2026-06-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_phase3_rag"
down_revision = "0002_phase2_ingestion"
branch_labels = None
depends_on = None

# Tenant CONTENT tables: owner-only isolation, NO admin bypass (ADR-0002).
_CONTENT_TABLES = ("conversations", "messages")

_MESSAGE_ROLE = ("user", "assistant")


def upgrade() -> None:
    op.execute("CREATE TYPE message_role AS ENUM " + _enum_values(_MESSAGE_ROLE))

    message_role = postgresql.ENUM(*_MESSAGE_ROLE, name="message_role", create_type=False)

    # ------------------------------------------------------- conversations
    op.create_table(
        "conversations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conversations_project_id", "conversations", ["project_id"])
    op.create_index("ix_conversations_owner_id", "conversations", ["owner_id"])

    # ------------------------------------------------------------- messages
    op.create_table(
        "messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("grounded", sa.Boolean(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column(
            "citations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_project_id", "messages", ["project_id"])

    _apply_rls()


def _apply_rls() -> None:
    """ENABLE + FORCE RLS with owner-only policies and NO admin bypass.

    ``conversations`` and ``messages`` hold tenant CONTENT (the questions and
    answers), so a mis-set ``app.is_admin`` GUC must never leak rows across
    tenants (ADR-0002). ``NULLIF(...,'')`` makes an unset GUC match no rows.
    """
    for table in _CONTENT_TABLES:
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


def _enum_values(values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{v}'" for v in values)
    return f"({rendered})"


def downgrade() -> None:
    for table in _CONTENT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_owner_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_messages_project_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_conversations_owner_id", table_name="conversations")
    op.drop_index("ix_conversations_project_id", table_name="conversations")
    op.drop_table("conversations")

    op.execute("DROP TYPE IF EXISTS message_role")
