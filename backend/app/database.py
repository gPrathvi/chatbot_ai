from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    chunks: Mapped[list["ChunkRow"]] = relationship(cascade="all, delete-orphan")


class ChunkRow(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required. Add your hosted PostgreSQL URL to backend/.env and restart the backend.")

_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine)


def init_database() -> None:
    Base.metadata.create_all(_engine)


def save_document(document: Any) -> None:
    with SessionLocal() as session:
        row = DocumentRow(id=document.id, filename=document.filename, file_type=document.file_type, size_bytes=document.size_bytes)
        row.chunks = [ChunkRow(id=chunk.id, document_id=document.id, filename=chunk.filename, text=chunk.text, page=chunk.page, embedding=chunk.embedding) for chunk in document.chunks]
        session.add(row)
        session.commit()


def load_documents() -> list[dict[str, object]]:
    with SessionLocal() as session:
        rows = session.query(DocumentRow).order_by(DocumentRow.created_at.desc()).all()
        return [{"id": row.id, "filename": row.filename, "file_type": row.file_type, "chunks": len(row.chunks)} for row in rows]


def load_chunks(document_ids: list[str] | None = None) -> list[Any]:
    with SessionLocal() as session:
        query = session.query(ChunkRow)
        if document_ids:
            query = query.filter(ChunkRow.document_id.in_(document_ids))
        return query.all()
