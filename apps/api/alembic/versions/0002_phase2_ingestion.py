"""Phase 2: ingestion schema, halfvec chunks, ingest jobs, operator key.

Creates the ``vector`` extension, the ``document_status`` / ``document_error_code``
PG enums, and the four Phase-2 tables: ``documents``, ``chunks``,
``ingest_jobs``, ``operator_default``. ``chunks.embedding`` is an unbounded
``halfvec`` (ADR-0003) and ``chunks.content_tsv`` is a generated/STORED
``tsvector('simple')`` (ADR-0004), with a GIN index on it plus a composite
``(owner_id, project_id)`` btree.

RLS (ADR-0002): ``documents`` and ``chunks`` are ENABLE + FORCE with **owner-only**
policies (``owner_id = NULLIF(current_setting('app.current_user_id', true),'')::uuid``)
and NO admin bypass — these are tenant *content* tables. The per-dim HNSW index is
deliberately NOT built here (deferred per ADR-0003); the store layer builds it
lazily on first ingest.

Revision ID: 0002_phase2_ingestion
Revises: 0001_phase1_auth_tenancy
Create Date: 2026-06-19
"""

from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_phase2_ingestion"
down_revision = "0001_phase1_auth_tenancy"
branch_labels = None
depends_on = None

# Tenant CONTENT tables: owner-only isolation, NO admin bypass.
_CONTENT_TABLES = ("documents", "chunks")

_DOC_STATUS = ("queued", "parsing", "chunking", "embedding", "ready", "failed")
_DOC_ERROR = (
    "OVERSIZE",
    "BAD_TYPE",
    "DECOMPRESSION_BOMB",
    "ENCRYPTED_PDF",
    "NO_TEXT",
    "PARSE_ERROR",
    "EMBED_ERROR",
    "TOO_MANY_CHUNKS",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("CREATE TYPE document_status AS ENUM " + _enum_values(_DOC_STATUS))
    op.execute("CREATE TYPE document_error_code AS ENUM " + _enum_values(_DOC_ERROR))

    document_status = postgresql.ENUM(*_DOC_STATUS, name="document_status", create_type=False)
    document_error_code = postgresql.ENUM(
        *_DOC_ERROR, name="document_error_code", create_type=False
    )

    # ------------------------------------------------------------- documents
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("mime", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("status", document_status, nullable=False, server_default="queued"),
        sa.Column("status_detail", sa.Text(), nullable=True),
        sa.Column("error_code", document_error_code, nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
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
        sa.UniqueConstraint("project_id", "content_sha256", name="uq_documents_project_sha256"),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])

    # ---------------------------------------------------------------- chunks
    op.create_table(
        "chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("section_path", sa.String(length=1024), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", HALFVEC(), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column(
            "content_tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', content)", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    # Composite btree for tenant-scoped retrieval (ARCHITECTURE.md section 5).
    op.create_index("ix_chunks_owner_project", "chunks", ["owner_id", "project_id"])
    # GIN on the generated tsvector for the keyword leg (ADR-0004).
    op.create_index("ix_chunks_content_tsv", "chunks", ["content_tsv"], postgresql_using="gin")
    # NOTE: the per-dim HNSW index is deferred (ADR-0003) and built lazily by
    # app.ingestion.store.ensure_hnsw_index on first ingest. Not created here.

    # ----------------------------------------------------------- ingest_jobs
    op.create_table(
        "ingest_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_cursor", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ingest_jobs_document_id", "ingest_jobs", ["document_id"])
    op.create_index("ix_ingest_jobs_owner_id", "ingest_jobs", ["owner_id"])

    # ------------------------------------------------------ operator_default
    op.create_table(
        "operator_default",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("key_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.UniqueConstraint("provider", name="uq_operator_default_provider"),
    )

    _apply_rls()


def _apply_rls() -> None:
    """ENABLE + FORCE RLS with owner-only policies and NO admin bypass.

    ``documents`` and ``chunks`` hold tenant CONTENT, so a mis-set ``app.is_admin``
    GUC must never leak rows across tenants (ADR-0002). ``NULLIF(...,'')`` makes
    an unset GUC match no rows rather than raising on an invalid uuid cast.
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

    op.drop_table("operator_default")
    op.drop_index("ix_ingest_jobs_owner_id", table_name="ingest_jobs")
    op.drop_index("ix_ingest_jobs_document_id", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")
    op.drop_index("ix_chunks_content_tsv", table_name="chunks")
    op.drop_index("ix_chunks_owner_project", table_name="chunks")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.execute("DROP INDEX IF EXISTS chunks_emb_768_hnsw")
    op.drop_table("chunks")
    op.drop_index("ix_documents_owner_id", table_name="documents")
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_table("documents")

    op.execute("DROP TYPE IF EXISTS document_error_code")
    op.execute("DROP TYPE IF EXISTS document_status")
