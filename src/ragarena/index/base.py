"""Index backend protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ..types import Chunk


class BaseIndex(ABC):
    """A searchable collection of chunks with dense and lexical legs."""

    name: str = "base"

    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.build_ms: float = 0.0
        self.embed_tokens: int = 0

    @abstractmethod
    async def build(self, chunks: list[Chunk]) -> None:
        """Embed and index ``chunks``. Replaces any previous contents."""

    @abstractmethod
    async def search_dense(self, query_vector: np.ndarray, k: int) -> list[tuple[int, float]]:
        """Return ``(chunk position, similarity)`` pairs, best first."""

    @abstractmethod
    def search_lexical(self, query: str, k: int) -> list[tuple[int, float]]:
        """Return ``(chunk position, BM25-style score)`` pairs, best first."""

    def chunk_at(self, position: int) -> Chunk:
        return self.chunks[position]

    @property
    def size(self) -> int:
        return len(self.chunks)

    async def aclose(self) -> None:
        return None
