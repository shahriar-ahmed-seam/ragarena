"""Index backends."""

from __future__ import annotations

from .base import BaseIndex
from .bm25 import BM25
from .memory import MemoryIndex

__all__ = ["BM25", "BaseIndex", "MemoryIndex", "build_index"]


def build_index(backend: str, embedder, *, database_url: str = "", run_id: str | None = None):
    """Instantiate an index backend by name (``memory`` or ``pgvector``)."""
    key = (backend or "memory").lower()
    if key in {"memory", "numpy", "inmemory"}:
        return MemoryIndex(embedder)
    if key in {"pgvector", "postgres", "pg"}:
        from .pgvector import PgVectorIndex

        return PgVectorIndex(embedder, database_url=database_url, run_id=run_id)
    from ..errors import ConfigError

    raise ConfigError(f"Unknown index backend {backend!r}. Expected: memory, pgvector.")
