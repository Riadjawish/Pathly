"""Storage abstraction with a secure local-development implementation."""

from __future__ import annotations

import asyncio
import codecs
import hashlib
import os
import re
import zipfile
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import uuid4

from .exceptions import StorageError, UploadValidationError

_CHUNK_SIZE = 1024 * 1024
_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._-]+")

ALLOWED_UPLOADS: dict[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf", "application/octet-stream"}),
    ".docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
            "application/octet-stream",
        }
    ),
    ".pptx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/zip",
            "application/octet-stream",
        }
    ),
    ".txt": frozenset({"text/plain", "application/octet-stream"}),
    ".md": frozenset(
        {"text/markdown", "text/x-markdown", "text/plain", "application/octet-stream"}
    ),
}


@runtime_checkable
class AsyncReadable(Protocol):
    """Minimal interface implemented by FastAPI/Starlette UploadFile."""

    async def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True, slots=True)
class StoredFile:
    key: str
    original_name: str
    content_type: str
    size_bytes: int
    sha256: str


@runtime_checkable
class StorageBackend(Protocol):
    """Backend contract; an S3 implementation can satisfy this unchanged."""

    async def save_upload(
        self,
        upload: AsyncReadable,
        *,
        filename: str,
        content_type: str | None,
        prefix: str = "materials",
    ) -> StoredFile: ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...

    def materialize(self, key: str) -> AbstractAsyncContextManager[Path]:
        """Yield a temporary local path to an object.

        Local storage yields its existing path. A future S3 backend can download to
        a temporary file and remove it when the context exits.
        """

        ...


def _clean_filename(filename: str) -> str:
    if not filename or "\x00" in filename:
        raise UploadValidationError("A valid file name is required.")
    clean = Path(filename.replace("\\", "/")).name.strip()
    if clean in {"", ".", ".."}:
        raise UploadValidationError("A valid file name is required.")
    return clean[:255]


def _clean_prefix(prefix: str) -> str:
    segments = []
    for raw in prefix.replace("\\", "/").split("/"):
        if not raw or raw in {".", ".."}:
            continue
        cleaned = _SAFE_SEGMENT.sub("-", raw).strip(".-_")
        if cleaned:
            segments.append(cleaned[:80])
    return "/".join(segments) or "materials"


def validate_upload_metadata(filename: str, content_type: str | None) -> tuple[str, str, str]:
    clean_name = _clean_filename(filename)
    extension = Path(clean_name).suffix.lower()
    if extension not in ALLOWED_UPLOADS:
        allowed = ", ".join(sorted(ALLOWED_UPLOADS))
        raise UploadValidationError(f"Unsupported file type. Allowed types: {allowed}.")

    normalized_type = (content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if normalized_type not in ALLOWED_UPLOADS[extension]:
        raise UploadValidationError(
            f"The declared content type {normalized_type!r} does not match a {extension} file."
        )
    return clean_name, extension, normalized_type


def _validate_signature(path: Path, extension: str) -> None:
    with path.open("rb") as stream:
        header = stream.read(8)

    if extension == ".pdf" and not header.startswith(b"%PDF-"):
        raise UploadValidationError("This file does not contain a valid PDF signature.")
    if extension in {".docx", ".pptx"}:
        if not header.startswith(b"PK"):
            raise UploadValidationError("This Office document is not a valid ZIP-based file.")
        expected = "word/" if extension == ".docx" else "ppt/"
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                if "[Content_Types].xml" not in names or not any(
                    name.startswith(expected) for name in names
                ):
                    raise UploadValidationError(
                        "This Office document has an invalid internal structure."
                    )
        except zipfile.BadZipFile as exc:
            raise UploadValidationError("This Office document is not a valid ZIP file.") from exc
    if extension in {".txt", ".md"}:
        try:
            with path.open("rb") as stream:
                stream.read(65536).decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise UploadValidationError("Text uploads must use UTF-8 encoding.") from exc


class LocalStorage:
    """Filesystem storage for development with an S3-compatible service contract."""

    def __init__(self, settings: object) -> None:
        raw_root = getattr(
            settings,
            "local_storage_path",
            getattr(settings, "storage_path", "./data/uploads"),
        )
        self.root = Path(raw_root).expanduser().resolve()
        maximum_mb = getattr(
            settings,
            "max_upload_size_mb",
            getattr(settings, "max_upload_mb", 25),
        )
        self.max_upload_bytes = int(maximum_mb) * 1024 * 1024
        if self.max_upload_bytes <= 0:
            raise StorageError("max_upload_size_mb must be greater than zero.")
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve_key(self, key: str) -> Path:
        if not key or "\x00" in key:
            raise StorageError("Invalid storage key.")
        candidate = (self.root / key).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise StorageError("Storage key escapes the configured storage root.") from exc
        return candidate

    async def save_upload(
        self,
        upload: AsyncReadable,
        *,
        filename: str,
        content_type: str | None,
        prefix: str = "materials",
    ) -> StoredFile:
        clean_name, extension, normalized_type = validate_upload_metadata(filename, content_type)
        key = f"{_clean_prefix(prefix)}/{uuid4().hex}{extension}"
        destination = self._resolve_key(key)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.part")
        await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)

        size = 0
        digest = hashlib.sha256()
        text_decoder = (
            codecs.getincrementaldecoder("utf-8-sig")("strict")
            if extension in {".txt", ".md"}
            else None
        )
        try:
            handle = await asyncio.to_thread(temporary.open, "xb")
            try:
                while True:
                    chunk = await upload.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.max_upload_bytes:
                        raise UploadValidationError(
                            "File is too large. Maximum size is "
                            f"{self.max_upload_bytes // (1024 * 1024)} MB."
                        )
                    if text_decoder is not None:
                        try:
                            text_decoder.decode(chunk, final=False)
                        except UnicodeDecodeError as exc:
                            raise UploadValidationError(
                                "Text uploads must use UTF-8 encoding."
                            ) from exc
                    digest.update(chunk)
                    await asyncio.to_thread(handle.write, chunk)
                if text_decoder is not None:
                    try:
                        text_decoder.decode(b"", final=True)
                    except UnicodeDecodeError as exc:
                        raise UploadValidationError(
                            "Text uploads must use UTF-8 encoding."
                        ) from exc
                await asyncio.to_thread(handle.flush)
                await asyncio.to_thread(os.fsync, handle.fileno())
            finally:
                await asyncio.to_thread(handle.close)

            if size == 0:
                raise UploadValidationError("The uploaded file is empty.")
            await asyncio.to_thread(_validate_signature, temporary, extension)
            await asyncio.to_thread(temporary.replace, destination)
        except UploadValidationError:
            await asyncio.to_thread(temporary.unlink, missing_ok=True)
            raise
        except asyncio.CancelledError:
            await asyncio.to_thread(temporary.unlink, missing_ok=True)
            raise
        except Exception as exc:
            await asyncio.to_thread(temporary.unlink, missing_ok=True)
            raise StorageError("The uploaded file could not be stored.") from exc

        return StoredFile(
            key=key,
            original_name=clean_name,
            content_type=normalized_type,
            size_bytes=size,
            sha256=digest.hexdigest(),
        )

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(self._resolve_key(key).unlink, missing_ok=True)
        except StorageError:
            raise
        except OSError as exc:
            raise StorageError("The stored file could not be deleted.") from exc

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._resolve_key(key).is_file)

    @asynccontextmanager
    async def materialize(self, key: str) -> AsyncIterator[Path]:
        path = self._resolve_key(key)
        if not await asyncio.to_thread(path.is_file):
            raise StorageError("The requested stored file does not exist.")
        yield path
