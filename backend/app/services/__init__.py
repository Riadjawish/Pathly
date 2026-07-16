"""Infrastructure and AI services for Pathly's API layer."""

from .chunking import Chunk, chunk_document
from .exceptions import (
    AIConfigurationError,
    AIResponseError,
    DocumentExtractionError,
    ServiceError,
    StorageError,
    UploadValidationError,
    VectorStoreError,
)
from .extraction import ExtractedDocument, ExtractedPage, extract_document
from .gemini import GeminiService
from .learning import LearningEngine
from .mailer import get_outbox, send_email
from .materials import MaterialProcessingResult, process_material
from .rag import RAGService
from .storage import LocalStorage, StorageBackend, StoredFile, validate_upload_metadata
from .vector_store import ChromaVectorStore, RetrievedChunk, VectorDocument, VectorStore

__all__ = [
    "AIConfigurationError",
    "AIResponseError",
    "ChromaVectorStore",
    "Chunk",
    "DocumentExtractionError",
    "ExtractedDocument",
    "ExtractedPage",
    "GeminiService",
    "LearningEngine",
    "LocalStorage",
    "MaterialProcessingResult",
    "RAGService",
    "RetrievedChunk",
    "ServiceError",
    "StorageBackend",
    "StorageError",
    "StoredFile",
    "UploadValidationError",
    "VectorDocument",
    "VectorStore",
    "VectorStoreError",
    "chunk_document",
    "extract_document",
    "get_outbox",
    "process_material",
    "send_email",
    "validate_upload_metadata",
]
