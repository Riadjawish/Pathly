from pathlib import Path

import pytest

from app.services import LocalStorage, UploadValidationError, chunk_document
from app.services.extraction import ExtractedDocument, ExtractedPage


class Upload:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.cursor = 0

    async def read(self, size: int = -1) -> bytes:
        if self.cursor >= len(self.content):
            return b""
        end = len(self.content) if size < 0 else self.cursor + size
        chunk = self.content[self.cursor : end]
        self.cursor = end
        return chunk


class StorageSettings:
    max_upload_size_mb = 1

    def __init__(self, path: Path) -> None:
        self.local_storage_path = str(path)


@pytest.mark.asyncio
async def test_local_storage_saves_safe_provider_neutral_key(tmp_path: Path) -> None:
    storage = LocalStorage(StorageSettings(tmp_path))
    stored = await storage.save_upload(
        Upload(b"Pathly notes"),
        filename="../week 1.md",
        content_type="text/markdown",
        prefix="user/subject",
    )
    assert stored.original_name == "week 1.md"
    assert stored.key.startswith("user/subject/")
    assert await storage.exists(stored.key)
    await storage.delete(stored.key)
    assert not await storage.exists(stored.key)


@pytest.mark.asyncio
async def test_local_storage_rejects_unsupported_files(tmp_path: Path) -> None:
    storage = LocalStorage(StorageSettings(tmp_path))
    with pytest.raises(UploadValidationError):
        await storage.save_upload(
            Upload(b"binary"),
            filename="malware.exe",
            content_type="application/octet-stream",
        )


def test_chunking_keeps_page_sources_and_overlap() -> None:
    text = "Sentence about calculus. " * 120
    document = ExtractedDocument(text=text, pages=(ExtractedPage(number=4, text=text),))
    chunks = chunk_document(document, max_chars=600, overlap_chars=80)
    assert len(chunks) > 1
    assert all(chunk.page_number == 4 for chunk in chunks)
    assert chunks[0].end_char > chunks[1].start_char
