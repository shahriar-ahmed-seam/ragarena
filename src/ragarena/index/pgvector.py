"""Postgres + pgvector index backend.

This is the production-shaped path: HNSW cosine index for the dense leg,
Postgres full-text `ts_rank_cd` for the lexical leg, both scoped to a single
run id so parallel benchmarks cannot see each other's rows.

Requires the optional extra: ``pip install "ragarena[pgvector]"`` and a
``DATABASE_URL`` pointing at Postgres with the `vector` extension available
(Neon, Supabase, RDS and local all work).
"""

from __future__ import annotations

import json
import uuid

import numpy as np

from ..errors import ConfigError, IndexError_
from ..types import Chunk
from ..utils import Timer
from .base import BaseIndex

_DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS ragarena_chunks (
    id          BIGSERIAL PRIMARY KEY,
    run_id      TEXT        NOT NULL,
    position    INTEGER     NOT NULL,
    chunk_id    TEXT        NOT NULL,
    doc_id      TEXT        NOT NULL,
    title       TEXT        NOT NULL DEFAULT '',
    body        TEXT        NOT NULL,
    metadata    JSONB       NOT NULL DEFAULT '{}'::jsonb,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED,
    embedding   vector(%(dim)s) NOT NULL,
    UNIQUE (run_id, position)
);

CREATE INDEX IF NOT EXISTS ragarena_chunks_run_idx ON ragarena_chunks (run_id);
CREATE INDEX IF NOT EXISTS ragarena_chunks_tsv_idx ON ragarena_chunks USING GIN (tsv);
"""

_HNSW = """
CREATE INDEX IF NOT EXISTS ragarena_chunks_embedding_idx
    ON ragarena_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
"""


def _vector_literal(vector: np.ndarray) -> str:
    return "[" + ",".join(f"{float(x):.7g}" for x in np.asarray(vector).reshape(-1)) + "]"


class PgVectorIndex(BaseIndex):
    name = "pgvector"

    def __init__(
        self,
        embedder,
        *,
        database_url: str,
        run_id: str | None = None,
        drop_on_close: bool = True,
        ef_search: int = 100,
    ) -> None:
        super().__init__()
        if not database_url:
            raise ConfigError("PgVectorIndex requires DATABASE_URL.")
        try:
            import psycopg  # noqa: F401
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ConfigError(
                'psycopg is not installed. Run: pip install "ragarena[pgvector]"'
            ) from exc
        self.embedder = embedder
        self.database_url = database_url
        self.run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
        self.drop_on_close = drop_on_close
        self.ef_search = ef_search
        self._conn = None

    # ----------------------------------------------------------------- conn
    def _connect(self):
        import psycopg

        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self.database_url, autocommit=True)
        return self._conn

    # ---------------------------------------------------------------- build
    async def build(self, chunks: list[Chunk]) -> None:
        self.chunks = list(chunks)
        if not self.chunks:
            return

        result = await self.embedder.embed([c.text for c in self.chunks], input_type="document")
        self.embed_tokens = result.tokens
        vectors = result.vectors
        dim = int(vectors.shape[1])

        with Timer() as timer:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute(_DDL % {"dim": dim})
                cur.execute(_HNSW)
                cur.execute("DELETE FROM ragarena_chunks WHERE run_id = %s", (self.run_id,))
                rows = [
                    (
                        self.run_id,
                        position,
                        chunk.id,
                        chunk.doc_id,
                        chunk.title,
                        chunk.text,
                        json.dumps(chunk.metadata),
                        _vector_literal(vectors[position]),
                    )
                    for position, chunk in enumerate(self.chunks)
                ]
                cur.executemany(
                    "INSERT INTO ragarena_chunks "
                    "(run_id, position, chunk_id, doc_id, title, body, metadata, embedding) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector)",
                    rows,
                )
                cur.execute("ANALYZE ragarena_chunks")
        self.build_ms = timer.ms

    # --------------------------------------------------------------- search
    async def search_dense(self, query_vector: np.ndarray, k: int) -> list[tuple[int, float]]:
        if not self.chunks:
            return []
        try:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute("SET LOCAL hnsw.ef_search = %s", (self.ef_search,))
                cur.execute(
                    "SELECT position, 1 - (embedding <=> %s::vector) AS similarity "
                    "FROM ragarena_chunks WHERE run_id = %s "
                    "ORDER BY embedding <=> %s::vector LIMIT %s",
                    (
                        _vector_literal(query_vector),
                        self.run_id,
                        _vector_literal(query_vector),
                        k,
                    ),
                )
                return [(int(pos), float(sim)) for pos, sim in cur.fetchall()]
        except Exception as exc:  # pragma: no cover - depends on live DB
            raise IndexError_(f"pgvector dense search failed: {exc}") from exc

    def search_lexical(self, query: str, k: int) -> list[tuple[int, float]]:
        if not self.chunks:
            return []
        try:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT position, ts_rank_cd(tsv, websearch_to_tsquery('english', %s)) AS rank "
                    "FROM ragarena_chunks "
                    "WHERE run_id = %s AND tsv @@ websearch_to_tsquery('english', %s) "
                    "ORDER BY rank DESC LIMIT %s",
                    (query, self.run_id, query, k),
                )
                return [(int(pos), float(rank)) for pos, rank in cur.fetchall()]
        except Exception as exc:  # pragma: no cover - depends on live DB
            raise IndexError_(f"pgvector lexical search failed: {exc}") from exc

    async def aclose(self) -> None:
        if self._conn is None or self._conn.closed:
            return
        if self.drop_on_close:
            with self._conn.cursor() as cur:
                cur.execute("DELETE FROM ragarena_chunks WHERE run_id = %s", (self.run_id,))
        self._conn.close()
        self._conn = None
