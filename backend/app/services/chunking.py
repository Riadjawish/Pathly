"""Deterministic and page-aware document chunking."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .extraction import ExtractedDocument


@dataclass(frozen=True, slots=True)
class Chunk:
    index: int
    text: str
    page_number: int | None
    start_char: int
    end_char: int
    token_estimate: int
    metadata: dict[str, Any] = field(default_factory=dict)


def _choose_boundary(text: str, start: int, hard_end: int, max_chars: int) -> int:
    if hard_end >= len(text):
        return len(text)
    minimum = start + int(max_chars * 0.58)
    for separator in ("\n\n", ". ", "? ", "! ", "\n", "; ", ", ", " "):
        boundary = text.rfind(separator, minimum, hard_end)
        if boundary >= minimum:
            return boundary + len(separator)
    return hard_end


def _windows(text: str, max_chars: int, overlap_chars: int) -> Iterator[tuple[int, int, str]]:
    cursor = 0
    length = len(text)
    while cursor < length:
        while cursor < length and text[cursor].isspace():
            cursor += 1
        if cursor >= length:
            break

        hard_end = min(length, cursor + max_chars)
        end = _choose_boundary(text, cursor, hard_end, max_chars)
        raw = text[cursor:end]
        chunk_text = raw.strip()
        if chunk_text:
            leading = len(raw) - len(raw.lstrip())
            trailing = len(raw.rstrip())
            yield cursor + leading, cursor + trailing, chunk_text

        if end >= length:
            break
        next_cursor = max(cursor + 1, end - overlap_chars)
        while next_cursor < end and not text[next_cursor].isspace():
            next_cursor += 1
        cursor = next_cursor


def chunk_document(
    document: ExtractedDocument,
    *,
    max_chars: int = 2400,
    overlap_chars: int = 280,
) -> list[Chunk]:
    """Split a document into overlapping chunks while retaining page/slide sources."""

    if max_chars < 500:
        raise ValueError("max_chars must be at least 500.")
    if overlap_chars < 0 or overlap_chars >= max_chars // 2:
        raise ValueError("overlap_chars must be non-negative and less than half max_chars.")

    chunks: list[Chunk] = []
    global_offset = 0
    pages = document.pages or ()
    if not pages and document.text:
        from .extraction import ExtractedPage

        pages = (ExtractedPage(number=1, text=document.text),)

    for page in pages:
        page_text = page.text.strip()
        if not page_text:
            continue
        for local_start, local_end, text in _windows(page_text, max_chars, overlap_chars):
            metadata: dict[str, Any] = {}
            if page.title:
                metadata["page_title"] = page.title
            chunks.append(
                Chunk(
                    index=len(chunks),
                    text=text,
                    page_number=page.number,
                    start_char=global_offset + local_start,
                    end_char=global_offset + local_end,
                    token_estimate=max(1, (len(text) + 3) // 4),
                    metadata=metadata,
                )
            )
        global_offset += len(page_text) + 2
    return chunks
