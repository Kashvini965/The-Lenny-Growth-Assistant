"""Initial schema: chat sessions, messages, artifacts, transcript index.

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("use_rag", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("session_metadata", sa.JSON(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_sessions_updated_at", "chat_sessions", ["updated_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("message_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_index("ix_messages_session_created", "messages", ["session_id", "created_at"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.String(length=36),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("artifact_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_artifacts_session_id", "artifacts", ["session_id"])

    op.create_table(
        "transcript_docs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=400), nullable=False),
        sa.Column("url", sa.String(length=800), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("author", sa.String(length=200), nullable=True),
        sa.Column("published_at", sa.String(length=64), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("doc_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("url", name="uq_transcript_docs_url"),
    )
    op.create_index("ix_transcript_docs_content_hash", "transcript_docs", ["content_hash"])

    op.create_table(
        "transcript_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "doc_id",
            sa.String(length=36),
            sa.ForeignKey("transcript_docs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_metadata", sa.JSON(), nullable=False),
        sa.UniqueConstraint("doc_id", "chunk_index", name="uq_transcript_chunks_doc_index"),
    )
    op.create_index("ix_transcript_chunks_doc_id", "transcript_chunks", ["doc_id"])
    op.create_index("ix_transcript_chunks_doc_chunk", "transcript_chunks", ["doc_id", "chunk_index"])

    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("documents_ingested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunks_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("run_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ingest_runs")
    op.drop_index("ix_transcript_chunks_doc_chunk", table_name="transcript_chunks")
    op.drop_index("ix_transcript_chunks_doc_id", table_name="transcript_chunks")
    op.drop_table("transcript_chunks")
    op.drop_index("ix_transcript_docs_content_hash", table_name="transcript_docs")
    op.drop_table("transcript_docs")
    op.drop_index("ix_artifacts_session_id", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_messages_session_created", table_name="messages")
    op.drop_index("ix_messages_session_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_chat_sessions_updated_at", table_name="chat_sessions")
    op.drop_table("chat_sessions")
