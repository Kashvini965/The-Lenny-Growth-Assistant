"""SQLAlchemy ORM models for The Lenny Growth Assistant.

Tables
------
* `chat_sessions`      - one row per conversation.
* `messages`           - every user/assistant/system message with metadata.
* `artifacts`          - generated Markdown / HTML documents attached to a chat.
* `transcript_docs`    - ingested source transcripts (Lenny's Podcast / Newsletter).
* `transcript_chunks`  - cleaned, chunked passages + embeddings (RAG index).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base with a shared JSON type.

    `JSON` maps to `JSONB` on PostgreSQL via `with_variant` below; we keep the
    portable `JSON` type so the SQLite fallback works identically.
    """


# --------------------------------------------------------------------------- #
# Chat domain
# --------------------------------------------------------------------------- #
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(200), default="New chat")
    provider: Mapped[str] = mapped_column(String(32), default="ollama")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    use_rag: Mapped[bool] = mapped_column(default=True)
    session_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
        lazy="selectin",
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Artifact.created_at",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_chat_sessions_updated_at", "updated_at"),)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Citations returned by the retriever for this assistant message.
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Extra info: retrieved chunk ids, token estimates, provider errors, etc.
    message_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[ChatSession] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_messages_session_created", "session_id", "created_at"),)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(16))  # report | essay | html | code
    title: Mapped[str] = mapped_column(String(200), default="Artifact")
    format: Mapped[str] = mapped_column(String(16), default="markdown")  # markdown | html
    content: Mapped[str] = mapped_column(Text)
    artifact_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[ChatSession] = relationship(back_populates="artifacts")


# --------------------------------------------------------------------------- #
# Knowledge base domain
# --------------------------------------------------------------------------- #
class TranscriptDoc(Base):
    __tablename__ = "transcript_docs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(400))
    url: Mapped[str] = mapped_column(String(800))
    source: Mapped[str] = mapped_column(String(64), default="lennys-podcast")
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    excerpt: Mapped[str] = mapped_column(Text, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    chunks: Mapped[list["TranscriptChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("url", name="uq_transcript_docs_url"),)


class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    doc_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("transcript_docs.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    # JSON-encoded embedding vector. Portable across PostgreSQL and SQLite;
    # see `app/rag/vector_store.py` for the brute-force cosine search.
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    embedding_dim: Mapped[int] = mapped_column(Integer, default=0)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    document: Mapped[TranscriptDoc] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_transcript_chunks_doc_chunk", "doc_id", "chunk_index"),
        UniqueConstraint("doc_id", "chunk_index", name="uq_transcript_chunks_doc_index"),
    )


class IngestRun(Base):
    """Audit trail for knowledge-base ingestion runs."""

    __tablename__ = "ingest_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source: Mapped[str] = mapped_column(String(64), default="lennys-podcast")
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    documents_ingested: Mapped[int] = mapped_column(Integer, default=0)
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="success")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


__all__ = [
    "Base",
    "ChatSession",
    "Message",
    "Artifact",
    "TranscriptDoc",
    "TranscriptChunk",
    "IngestRun",
    "utcnow",
    "new_uuid",
]
