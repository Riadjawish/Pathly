"""Google Gemini client wrapper with strict JSON parsing and clear failures."""

from __future__ import annotations

import asyncio
import json
import random
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, TypeVar

from .exceptions import AIConfigurationError, AIResponseError

T = TypeVar("T")


def _setting(settings: object, name: str) -> str:
    raw_value = getattr(settings, name, "")
    reveal = getattr(raw_value, "get_secret_value", None)
    if callable(reveal):
        raw_value = reveal()
    value = str(raw_value or "").strip()
    if not value:
        raise AIConfigurationError(f"{name} is not configured.")
    return value


def _response_text(response: object) -> str:
    try:
        value = response.text  # type: ignore[attr-defined]
    except Exception as exc:
        raise AIResponseError("Gemini returned a response without readable text.") from exc
    if not isinstance(value, str) or not value.strip():
        raise AIResponseError("Gemini returned an empty response.")
    return value.strip()


def _balanced_json_slice(text: str) -> str | None:
    """Find the first balanced JSON object/array while respecting quoted strings."""

    start = next((index for index, char in enumerate(text) if char in "[{"), None)
    if start is None:
        return None
    opening = text[start]
    closing = "]" if opening == "[" else "}"
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def parse_json_response(text: str) -> dict[str, Any] | list[Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        sliced = _balanced_json_slice(candidate)
        if sliced is None:
            raise AIResponseError("Gemini did not return valid JSON.") from None
        try:
            parsed = json.loads(sliced)
        except json.JSONDecodeError as exc:
            raise AIResponseError("Gemini returned malformed JSON.") from exc

    if not isinstance(parsed, dict | list):
        raise AIResponseError("Gemini returned JSON with an unexpected root type.")
    return parsed


class GeminiService:
    """Async interface to Gemini generation and embeddings.

    The SDK is imported lazily so non-AI API routes can still start and report a
    useful configuration error when the optional dependency or API key is missing.
    """

    def __init__(self, settings: object) -> None:
        self._settings = settings
        self._client: Any | None = None
        self._types: Any | None = None
        self._attempts = max(1, int(getattr(settings, "gemini_retry_attempts", 3)))

    @property
    def generation_model(self) -> str:
        return str(
            getattr(
                self._settings,
                "gemini_generation_model",
                getattr(self._settings, "gemini_chat_model", ""),
            )
            or ""
        ).strip()

    @property
    def embedding_model(self) -> str:
        return str(getattr(self._settings, "gemini_embedding_model", "") or "").strip()

    def _ensure_client(self) -> tuple[Any, Any]:
        if self._client is not None and self._types is not None:
            return self._client, self._types
        api_key = _setting(self._settings, "gemini_api_key")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise AIConfigurationError("Gemini support requires the google-genai package.") from exc
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=60_000),
        )
        self._types = types
        return self._client, self._types

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        try:
            code = int(code)
        except (TypeError, ValueError):
            return False
        return code in {408, 409, 429, 500, 502, 503, 504}

    async def _with_retry(self, operation: Callable[[], Awaitable[T]]) -> T:
        last_error: Exception | None = None
        for attempt in range(self._attempts):
            try:
                return await operation()
            except Exception as exc:
                last_error = exc
                if attempt + 1 >= self._attempts or not self._is_retryable(exc):
                    break
                backoff = min(10.0, 0.5 * (2**attempt))
                await asyncio.sleep(backoff + random.uniform(0, backoff * 0.5))
        raise AIResponseError("Gemini could not complete the request.") from last_error

    async def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
    ) -> str:
        if not prompt.strip():
            raise ValueError("prompt cannot be empty.")
        client, types = self._ensure_client()
        model = self.generation_model
        if not model:
            raise AIConfigurationError("gemini_generation_model is not configured.")
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=max(0.0, min(1.0, temperature)),
            max_output_tokens=max(64, max_output_tokens),
        )

        async def operation() -> Any:
            return await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )

        return _response_text(await self._with_retry(operation))

    async def generate_json(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        temperature: float = 0.15,
        max_output_tokens: int = 6144,
    ) -> dict[str, Any] | list[Any]:
        if not prompt.strip():
            raise ValueError("prompt cannot be empty.")
        client, types = self._ensure_client()
        model = self.generation_model
        if not model:
            raise AIConfigurationError("gemini_generation_model is not configured.")
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=max(0.0, min(1.0, temperature)),
            max_output_tokens=max(64, max_output_tokens),
            response_mime_type="application/json",
        )

        async def operation() -> Any:
            return await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )

        return parse_json_response(_response_text(await self._with_retry(operation)))

    async def embed_texts(
        self,
        texts: Sequence[str],
        *,
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        cleaned = [text.strip() for text in texts]
        if not cleaned or any(not text for text in cleaned):
            raise ValueError("Embedding inputs cannot be empty.")
        client, types = self._ensure_client()
        model = self.embedding_model
        if not model:
            raise AIConfigurationError("gemini_embedding_model is not configured.")
        dimensions = int(getattr(self._settings, "gemini_embedding_dimensions", 768))
        is_embedding_2 = model.startswith("gemini-embedding-2")

        if is_embedding_2:
            prefix = (
                "task: search result | query: "
                if task_type == "RETRIEVAL_QUERY"
                else "title: none | text: "
            )
            config = types.EmbedContentConfig(output_dimensionality=dimensions)
            semaphore = asyncio.Semaphore(4)

            async def embed_one(text: str) -> list[float]:
                async with semaphore:

                    async def operation() -> Any:
                        return await client.aio.models.embed_content(
                            model=model,
                            contents=f"{prefix}{text}",
                            config=config,
                        )

                    response = await self._with_retry(operation)
                    embeddings = getattr(response, "embeddings", None)
                    if not embeddings or len(embeddings) != 1:
                        raise AIResponseError("Gemini returned an invalid embedding response.")
                    values = getattr(embeddings[0], "values", None)
                    if not values:
                        raise AIResponseError("Gemini returned an empty embedding.")
                    return [float(value) for value in values]

            return list(await asyncio.gather(*(embed_one(text) for text in cleaned)))

        config = types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=dimensions,
        )

        async def operation() -> Any:
            return await client.aio.models.embed_content(
                model=model,
                contents=cleaned,
                config=config,
            )

        response = await self._with_retry(operation)
        embeddings = getattr(response, "embeddings", None)
        if not embeddings or len(embeddings) != len(cleaned):
            raise AIResponseError("Gemini returned an unexpected number of embeddings.")
        vectors: list[list[float]] = []
        for embedding in embeddings:
            values = getattr(embedding, "values", None)
            if not values:
                raise AIResponseError("Gemini returned an empty embedding.")
            vectors.append([float(value) for value in values])
        return vectors

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_texts([query], task_type="RETRIEVAL_QUERY")
        return vectors[0]

    async def aclose(self) -> None:
        if self._client is None:
            return
        aio_client = getattr(self._client, "aio", None)
        close = getattr(aio_client, "aclose", None)
        if close is not None:
            result = close()
            if asyncio.iscoroutine(result):
                await result
