"""Embedding providers: Voyage AI (hosted), fastembed (local CPU), hash (offline).

All three return L2-normalised float32 vectors, so cosine similarity is a dot
product and the index code never needs to know which provider produced them.
"""

from __future__ import annotations

import hashlib

import numpy as np

from ..cache import ResponseCache
from ..errors import ConfigError, ProviderError
from ..utils import batched, estimate_tokens, tokenize
from .base import EmbedResult, HTTPProviderBase, l2_normalise

# Default output dimension of the voyage-4 family.
VOYAGE_DEFAULT_DIM = 1024

VOYAGE_MAX_BATCH = 1000


class VoyageEmbeddings(HTTPProviderBase):
    """Hosted embeddings via https://api.voyageai.com/v1/embeddings.

    ``input_type`` matters: Voyage prepends a different instruction for queries
    versus documents, which is worth a measurable chunk of retrieval quality.
    """

    name = "voyage"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "voyage-4-lite",
        dimension: int | None = None,
        batch_size: int = 96,
        timeout_s: float = 120.0,
        max_retries: int = 4,
        retry_base_delay_s: float = 1.5,
        cache: ResponseCache | None = None,
        rpm: int = 0,
    ) -> None:
        if not api_key:
            raise ConfigError("VoyageEmbeddings requires an API key (VOYAGE_API_KEY).")
        super().__init__(
            base_url="https://api.voyageai.com/v1",
            api_key=api_key,
            timeout_s=timeout_s,
            max_retries=max_retries,
            retry_base_delay_s=retry_base_delay_s,
            cache=cache,
            rpm=rpm,
        )
        self.model = model
        self._dimension = dimension or VOYAGE_DEFAULT_DIM
        self.batch_size = min(max(1, batch_size), VOYAGE_MAX_BATCH)
        self._explicit_dimension = dimension
        self.name = f"voyage:{model}"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str], *, input_type: str = "document") -> EmbedResult:
        if not texts:
            return EmbedResult(vectors=np.zeros((0, self._dimension), dtype=np.float32), model=self.model)

        vectors: list[np.ndarray] = []
        total_tokens = 0
        all_cached = True

        for batch in batched(texts, self.batch_size):
            payload: dict[str, object] = {
                "input": list(batch),
                "model": self.model,
                "input_type": input_type,
                "truncation": True,
            }
            if self._explicit_dimension:
                payload["output_dimension"] = self._explicit_dimension

            cache_key = None
            if self.cache is not None:
                cache_key = ResponseCache.make_key("embed", self.model, payload)
                hit = self.cache.get(cache_key)
                if hit is not None:
                    vectors.append(np.asarray(hit["vectors"], dtype=np.float32))
                    total_tokens += int(hit.get("tokens", 0))
                    continue

            all_cached = False
            body = await self._post("/embeddings", payload)
            data = body.get("data") or []
            if len(data) != len(batch):
                raise ProviderError(
                    self.name, f"expected {len(batch)} embeddings, got {len(data)}"
                )
            ordered = sorted(data, key=lambda d: int(d.get("index", 0)))
            matrix = l2_normalise(np.asarray([d["embedding"] for d in ordered], dtype=np.float32))
            tokens = int((body.get("usage") or {}).get("total_tokens") or 0)
            vectors.append(matrix)
            total_tokens += tokens
            self._dimension = matrix.shape[1]

            if self.cache is not None and cache_key is not None:
                self.cache.set(
                    cache_key,
                    "embed",
                    self.model,
                    {"vectors": matrix.tolist(), "tokens": tokens},
                )

        stacked = np.vstack(vectors) if vectors else np.zeros((0, self._dimension), dtype=np.float32)
        self._dimension = stacked.shape[1] if stacked.size else self._dimension
        return EmbedResult(
            vectors=stacked, tokens=total_tokens, model=self.model, cached=all_cached
        )


class FastEmbedEmbeddings:
    """Local CPU embeddings through `fastembed` (ONNX). No API key, no network.

    Install with ``pip install "ragarena[local]"``. Default model
    ``BAAI/bge-small-en-v1.5`` is 384-dim and ~130 MB on disk.
    """

    name = "fastembed"

    def __init__(
        self,
        *,
        model: str = "BAAI/bge-small-en-v1.5",
        cache_dir: str | None = None,
        threads: int | None = None,
    ) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ConfigError(
                "fastembed is not installed. Run: pip install \"ragarena[local]\""
            ) from exc
        self.model = model
        self._encoder = TextEmbedding(model_name=model, cache_dir=cache_dir, threads=threads)
        probe = np.asarray(
            next(iter(self._encoder.embed(["dimension probe"]))), dtype=np.float32
        )
        self._dimension = int(probe.shape[0])
        self.name = f"fastembed:{model}"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str], *, input_type: str = "document") -> EmbedResult:
        if not texts:
            return EmbedResult(
                vectors=np.zeros((0, self._dimension), dtype=np.float32), model=self.model
            )
        # bge-style models expect an instruction prefix on queries only.
        prepared = (
            [f"Represent this sentence for searching relevant passages: {t}" for t in texts]
            if input_type == "query" and "bge" in self.model.lower()
            else list(texts)
        )
        raw = list(self._encoder.embed(prepared))
        matrix = l2_normalise(np.asarray(raw, dtype=np.float32))
        return EmbedResult(
            vectors=matrix,
            tokens=sum(estimate_tokens(t) for t in prepared),
            model=self.model,
        )

    async def aclose(self) -> None:
        return None


class HashEmbeddings:
    """Deterministic hashed bag-of-words vectors. Offline, instant, no deps.

    Retrieval quality is poor by design. This exists so CI and contributors can
    exercise the whole pipeline without credentials, and so the leaderboard has
    an honest lower bound to compare real embedding models against.
    """

    name = "hash"

    def __init__(self, *, model: str = "hash-1024", dimension: int = 1024) -> None:
        self.model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dimension, dtype=np.float32)
        terms = tokenize(text)
        for term in terms:
            digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % self._dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        return vec

    async def embed(self, texts: list[str], *, input_type: str = "document") -> EmbedResult:
        if not texts:
            return EmbedResult(
                vectors=np.zeros((0, self._dimension), dtype=np.float32), model=self.model
            )
        matrix = l2_normalise(np.asarray([self._vector(t) for t in texts], dtype=np.float32))
        return EmbedResult(
            vectors=matrix, tokens=sum(estimate_tokens(t) for t in texts), model=self.model
        )

    async def aclose(self) -> None:
        return None
