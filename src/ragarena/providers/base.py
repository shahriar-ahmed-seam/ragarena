"""Provider protocols plus a shared HTTP client with retries and caching."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx
import numpy as np

from ..cache import ResponseCache
from ..errors import ProviderError, RateLimitError

RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 529}


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_prompt_tokens: int = 0
    model: str = ""
    cached: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbedResult:
    vectors: np.ndarray  # shape (n, dim), float32, L2-normalised
    tokens: int = 0
    model: str = ""
    cached: bool = False


@dataclass
class RerankResult:
    # (original index, relevance score), sorted by score descending
    ranking: list[tuple[int, float]]
    tokens: int = 0
    model: str = ""
    cached: bool = False


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResponse: ...

    async def aclose(self) -> None: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    model: str

    @property
    def dimension(self) -> int: ...

    async def embed(self, texts: list[str], *, input_type: str = "document") -> EmbedResult: ...

    async def aclose(self) -> None: ...


@runtime_checkable
class RerankProvider(Protocol):
    name: str
    model: str

    async def rerank(
        self, query: str, documents: list[str], *, top_k: int | None = None
    ) -> RerankResult: ...

    async def aclose(self) -> None: ...


class AsyncRateLimiter:
    """Serialising limiter that enforces a minimum gap between requests.

    Free provider tiers can be as tight as 3 requests per minute. Discovering
    that through a wall of 429s wastes a run, so set the known limit and let the
    client pace itself. ``rpm <= 0`` disables pacing entirely.
    """

    def __init__(self, rpm: int) -> None:
        self.min_interval = 60.0 / rpm if rpm and rpm > 0 else 0.0
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def acquire(self) -> None:
        if self.min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next_allowed = now + self.min_interval


def l2_normalise(matrix: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalisation so cosine similarity is a plain dot product."""
    arr = np.asarray(matrix, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (arr / norms).astype(np.float32)


class HTTPProviderBase:
    """Shared async HTTP plumbing: one client, bounded retries, optional cache."""

    name = "http"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_s: float = 180.0,
        max_retries: int = 4,
        retry_base_delay_s: float = 1.5,
        cache: ResponseCache | None = None,
        extra_headers: dict[str, str] | None = None,
        rpm: int = 0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.max_retries = max_retries
        self.retry_base_delay_s = retry_base_delay_s
        self.cache = cache
        self.limiter = AsyncRateLimiter(rpm)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ragarena/0.1",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if extra_headers:
            headers.update(extra_headers)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout_s, connect=20.0),
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST JSON with exponential backoff + jitter on transient failures."""
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            await self.limiter.acquire()
            try:
                response = await self._client.post(path, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    raise ProviderError(self.name, f"transport failure: {exc}") from exc
                await self._sleep(attempt)
                continue

            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError as exc:
                    raise ProviderError(
                        self.name, f"malformed JSON response: {response.text[:200]}"
                    ) from exc

            detail = self._error_detail(response)
            if response.status_code in RETRY_STATUS and attempt < self.max_retries:
                retry_after = self._retry_after(response)
                await self._sleep(attempt, retry_after)
                continue
            if response.status_code == 429:
                raise RateLimitError(self.name, detail, status=429)
            raise ProviderError(self.name, detail, status=response.status_code)

        raise ProviderError(self.name, f"exhausted retries: {last_error}")

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text[:300]
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                return str(err.get("message") or err)
            if isinstance(err, str):
                return err
            for key in ("message", "detail", "detail_message"):
                if key in body:
                    return str(body[key])
        return str(body)[:300]

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        raw = response.headers.get("retry-after")
        if not raw:
            return None
        try:
            return min(30.0, float(raw))
        except ValueError:
            return None

    async def _sleep(self, attempt: int, retry_after: float | None = None) -> None:
        delay = (
            retry_after
            if retry_after is not None
            else self.retry_base_delay_s * (2**attempt)
        )
        await asyncio.sleep(min(45.0, delay) + random.uniform(0, 0.4))

    async def aclose(self) -> None:
        await self._client.aclose()
