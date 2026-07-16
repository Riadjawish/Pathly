from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.subject import Subject


class MaterialKind(str, Enum):
    COURSE = "course"
    NOTES = "notes"
    PRACTICE = "practice"
    EXAMS = "exams"


class ProcessingStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Material(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "materials"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="size_nonnegative"),
        CheckConstraint("page_count IS NULL OR page_count >= 0", name="page_count_nonnegative"),
    )

    subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[MaterialKind] = mapped_column(
        SAEnum(
            MaterialKind,
            name="material_kind",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=MaterialKind.COURSE,
        nullable=False,
    )
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[ProcessingStatus] = mapped_column(
        SAEnum(
            ProcessingStatus,
            name="processing_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=ProcessingStatus.UPLOADED,
        index=True,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    extracted_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    subject: Mapped[Subject] = relationship(back_populates="materials")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="material", cascade="all, delete-orphan", passive_deletes=True
    )


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("material_id", "chunk_index", name="uq_document_chunk_order"),
        CheckConstraint("chunk_index >= 0", name="chunk_index_nonnegative"),
        CheckConstraint("token_count >= 0", name="token_count_nonnegative"),
    )

    material_id: Mapped[UUID] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    vector_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    material: Mapped[Material] = relationship(back_populates="chunks")
    subject: Mapped[Subject] = relationship()


# Compatibility for code written against the initial internal name.
MaterialCategory = MaterialKind
