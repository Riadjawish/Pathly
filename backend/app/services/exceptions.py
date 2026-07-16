"""Service-layer exception hierarchy for route-safe error handling.

Routes can translate these exceptions into stable HTTP errors without coupling the
service layer to FastAPI.
"""


class ServiceError(RuntimeError):
    """Base class for an expected service failure."""


class StorageError(ServiceError):
    """A storage backend could not complete an operation."""


class UploadValidationError(StorageError, ValueError):
    """An uploaded file is unsupported, unsafe, or too large."""


class DocumentExtractionError(ServiceError):
    """Text could not be extracted from a supported document."""


class AIConfigurationError(ServiceError):
    """The AI provider is not configured or its SDK is unavailable."""


class AIResponseError(ServiceError):
    """The AI provider returned an empty or invalid response."""


class VectorStoreError(ServiceError):
    """The vector store is not configured or an operation failed."""
