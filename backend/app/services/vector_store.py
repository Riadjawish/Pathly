"""Vector-store contract with a persistent Chroma implementation."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .exceptions import VectorStoreError

ScalarMetadata = str | int | float | bool


@dataclass(frozen=True, slots=True)
class VectorDocument:
    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, ScalarMetadata] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    id: str
    text: str
    score: float
    metadata: dict[str, Any]


@runtime_checkable
class VectorStore(Protocol):
    async def upsert(self, documents: Sequence[VectorDocument]) -> None: ...

    async def query(
        self,
        embedding: Sequence[float],
        *,
        subject_id: str,
        limit: int = 8,
    ) -> list[RetrievedChunk]: ...

    async def list_subject(self, subject_id: str, *, limit: int = 100) -> list[RetrievedChunk]: ...

    async def delete_material(self, material_id: str) -> None: ...

    async def delete_subject(self, subject_id: str) -> None: ...


def _collection_name(raw: object) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", str(raw or "pathly-chunks")).strip(".-")
    value = value[:63]
    if len(value) < 3:
        value = "pathly-chunks"
    return value


def _clean_metadata(metadata: Mapping[str, object]) -> dict[str, ScalarMetadata]:
    clean: dict[str, ScalarMetadata] = {}
    for key, value in metadata.items():
        if isinstance(value, str | int | float | bool):
            clean[str(key)] = value
        elif value is not None:
            clean[str(key)] = str(value)
    return clean or {"source": "pathly"}


class ChromaVectorStore:
    """Local persistent Chroma store, isolated behind a replaceable interface."""

    def __init__(self, settings: object) -> None:
        raw_path = getattr(settings, "chroma_path", "./data/chroma")
        self.path = Path(raw_path).expanduser().resolve()
        self.name = _collection_name(getattr(settings, "chroma_collection", "pathly-chunks"))
        self._client: Any | None = None
        self._chroma_collection: Any | None = None
        self._lock = asyncio.Lock()

    def _collection(self) -> Any:
        if self._chroma_collection is not None:
            return self._chroma_collection
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError as exc:
            raise VectorStoreError("Vector search requires the chromadb package.") from exc
        try:
            self.path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._chroma_collection = self._client.get_or_create_collection(
                name=self.name,
                metadata={"hnsw:space": "cosine"},
            )
            return self._chroma_collection
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(
                "Chroma could not initialize its persistent collection."
            ) from exc

    async def _run(self, operation: Any) -> Any:
        async with self._lock:
            try:
                return await asyncio.to_thread(operation)
            except VectorStoreError:
                raise
            except Exception as exc:
                raise VectorStoreError("The vector-store operation failed.") from exc

    async def upsert(self, documents: Sequence[VectorDocument]) -> None:
        if not documents:
            return
        ids: list[str] = []
        texts: list[str] = []
        embeddings: list[list[float]] = []
        metadatas: list[dict[str, ScalarMetadata]] = []
        dimension: int | None = None
        seen: set[str] = set()
        for document in documents:
            if not document.id or document.id in seen:
                raise VectorStoreError("Vector document IDs must be unique and non-empty.")
            if not document.text.strip() or not document.embedding:
                raise VectorStoreError("Vector documents require text and an embedding.")
            if dimension is None:
                dimension = len(document.embedding)
            elif len(document.embedding) != dimension:
                raise VectorStoreError("All embeddings in a batch must share one dimension.")
            seen.add(document.id)
            ids.append(document.id)
            texts.append(document.text)
            embeddings.append([float(value) for value in document.embedding])
            metadatas.append(_clean_metadata(document.metadata))

        def operation() -> None:
            self._collection().upsert(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )

        await self._run(operation)

    async def query(
        self,
        embedding: Sequence[float],
        *,
        subject_id: str,
        limit: int = 8,
    ) -> list[RetrievedChunk]:
        if not embedding:
            raise VectorStoreError("A query embedding is required.")
        if not subject_id:
            raise VectorStoreError("subject_id is required for isolated retrieval.")
        count = max(1, min(int(limit), 50))

        def operation() -> dict[str, Any]:
            return self._collection().query(
                query_embeddings=[[float(value) for value in embedding]],
                n_results=count,
                where={"subject_id": str(subject_id)},
                include=["documents", "metadatas", "distances"],
            )

        result = await self._run(operation)
        ids = (result.get("ids") or [[]])[0]
        texts = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        retrieved: list[RetrievedChunk] = []
        for index, chunk_id in enumerate(ids):
            distance = float(distances[index]) if index < len(distances) else 1.0
            retrieved.append(
                RetrievedChunk(
                    id=str(chunk_id),
                    text=str(texts[index] if index < len(texts) else ""),
                    score=max(-1.0, min(1.0, 1.0 - distance)),
                    metadata=dict(metadatas[index] or {}) if index < len(metadatas) else {},
                )
            )
        return retrieved

    async def list_subject(self, subject_id: str, *, limit: int = 100) -> list[RetrievedChunk]:
        if not subject_id:
            raise VectorStoreError("subject_id is required.")
        count = max(1, min(int(limit), 1000))

        def operation() -> dict[str, Any]:
            return self._collection().get(
                where={"subject_id": str(subject_id)},
                limit=count,
                include=["documents", "metadatas"],
            )

        result = await self._run(operation)
        ids = result.get("ids") or []
        texts = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        return [
            RetrievedChunk(
                id=str(chunk_id),
                text=str(texts[index] if index < len(texts) else ""),
                score=1.0,
                metadata=dict(metadatas[index] or {}) if index < len(metadatas) else {},
            )
            for index, chunk_id in enumerate(ids)
        ]

    async def delete_material(self, material_id: str) -> None:
        if not material_id:
            return

        def operation() -> None:
            self._collection().delete(where={"material_id": str(material_id)})

        await self._run(operation)

    async def delete_subject(self, subject_id: str) -> None:
        if not subject_id:
            return

        def operation() -> None:
            self._collection().delete(where={"subject_id": str(subject_id)})

        await self._run(operation)
