"""In-process index: exact dense search over a numpy matrix + in-package BM25.

Exact search removes ANN recall as a confounder, so a strategy comparison
measures the strategy rather than index tuning. At benchmark corpus sizes
(thousands of chunks) a single matrix multiply is also faster than any ANN
structure. Swap in :class:`~ragarena.index.pgvector.PgVectorIndex` to measure
the production path.
"""

from __future__ import annotations

import numpy as np

from ..types import Chunk
from ..utils import Timer
from .base import BaseIndex
from .bm25 import BM25


class MemoryIndex(BaseIndex):
    name = "memory"

    def __init__(self, embedder, *, k1: float = 1.5, b: float = 0.75) -> None:
        super().__init__()
        self.embedder = embedder
        self._matrix: np.ndarray | None = None
        self._bm25: BM25 | None = None
        self._k1 = k1
        self._b = b

    async def build(self, chunks: list[Chunk]) -> None:
        self.chunks = list(chunks)
        if not self.chunks:
            self._matrix = None
            self._bm25 = None
            return

        with Timer() as timer:
            result = await self.embedder.embed(
                [c.text for c in self.chunks], input_type="document"
            )
            self._matrix = result.vectors
            self._bm25 = BM25([c.text for c in self.chunks], k1=self._k1, b=self._b)
        self.build_ms = timer.ms
        self.embed_tokens = result.tokens

    async def search_dense(self, query_vector: np.ndarray, k: int) -> list[tuple[int, float]]:
        if self._matrix is None or not len(self.chunks):
            return []
        vector = np.asarray(query_vector, dtype=np.float32).reshape(-1)
        # Vectors are L2-normalised on ingest, so a dot product is cosine.
        sims = self._matrix @ vector
        k = min(k, sims.shape[0])
        if k <= 0:
            return []
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]
        return [(int(i), float(sims[i])) for i in top]

    def search_lexical(self, query: str, k: int) -> list[tuple[int, float]]:
        if self._bm25 is None:
            return []
        return self._bm25.top_k(query, k)
