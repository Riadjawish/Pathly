"""End-to-end material extraction, chunking, embedding, and indexing pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .chunking import chunk_document
from .extraction import extract_document
from .learning import LearningEngine
from .storage import StorageBackend


@dataclass(frozen=True, slots=True)
class MaterialProcessingResult:
    extracted_characters: int
    page_count: int
    chunk_count: int
    indexed_chunks: int


async def process_material(
    *,
    storage: StorageBackend,
    learning: LearningEngine,
    storage_key: str,
    subject_id: str,
    material_id: str,
    material_name: str,
    max_chunk_chars: int = 2400,
    overlap_chars: int = 280,
) -> MaterialProcessingResult:
    """Process one stored document without depending on database model classes."""

    async with storage.materialize(storage_key) as path:
        document = await extract_document(path)
    chunks = chunk_document(
        document,
        max_chars=max_chunk_chars,
        overlap_chars=overlap_chars,
    )
    indexing = await learning.index_chunks(
        subject_id=subject_id,
        material_id=material_id,
        material_name=material_name,
        chunks=chunks,
    )
    return MaterialProcessingResult(
        extracted_characters=len(document.text),
        page_count=len(document.pages),
        chunk_count=len(chunks),
        indexed_chunks=indexing["indexed_chunks"],
    )
