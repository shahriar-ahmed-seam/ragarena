"""Retrieval strategies.

Rather than a class per technique (which explodes combinatorially), RAGArena
models retrieval as one configurable pipeline:

    query transform -> dense / lexical retrieval -> fusion -> dedupe -> rerank

A "strategy" is a named point in that configuration space. Named presets live
in :mod:`ragarena.presets`; anything you can express in :class:`PipelineConfig`
can be benchmarked without writing code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from .errors import StrategyError
from .fusion import dedupe_by_document, reciprocal_rank_fusion, weighted_score_fusion
from .index.base import BaseIndex
from .types import RetrievedChunk, Usage
from .utils import Timer, estimate_tokens, extract_json_object

Retriever = Literal["dense", "lexical", "hybrid"]
QueryTransform = Literal["none", "hyde", "multiquery"]
Fusion = Literal["rrf", "weighted"]


@dataclass
class PipelineConfig:
    """Every knob that defines a retrieval strategy."""

    retriever: Retriever = "hybrid"
    query_transform: QueryTransform = "none"
    rerank: bool = False

    top_k: int = 5
    candidate_k: int = 20

    fusion: Fusion = "rrf"
    dense_weight: float = 1.0
    lexical_weight: float = 1.0

    max_per_doc: int = 0  # 0 disables the per-document cap
    multiquery_n: int = 3
    hyde_max_words: int = 120

    def validate(self) -> None:
        if self.top_k <= 0:
            raise StrategyError("top_k must be positive")
        if self.candidate_k < self.top_k:
            raise StrategyError("candidate_k must be >= top_k")
        if self.retriever not in {"dense", "lexical", "hybrid"}:
            raise StrategyError(f"unknown retriever {self.retriever!r}")
        if self.query_transform not in {"none", "hyde", "multiquery"}:
            raise StrategyError(f"unknown query_transform {self.query_transform!r}")
        if self.fusion not in {"rrf", "weighted"}:
            raise StrategyError(f"unknown fusion {self.fusion!r}")
        if self.retriever == "lexical" and self.query_transform == "hyde":
            raise StrategyError("HyDE only affects dense retrieval; pair it with dense or hybrid")

    def as_dict(self) -> dict[str, Any]:
        return {
            "retriever": self.retriever,
            "query_transform": self.query_transform,
            "rerank": self.rerank,
            "top_k": self.top_k,
            "candidate_k": self.candidate_k,
            "fusion": self.fusion,
            "dense_weight": self.dense_weight,
            "lexical_weight": self.lexical_weight,
            "max_per_doc": self.max_per_doc,
            "multiquery_n": self.multiquery_n,
        }


@dataclass
class RetrievalOutcome:
    chunks: list[RetrievedChunk]
    usage: Usage = field(default_factory=Usage)
    embed_query_ms: float = 0.0
    retrieve_ms: float = 0.0
    rerank_ms: float = 0.0
    transform_ms: float = 0.0
    expanded_queries: list[str] = field(default_factory=list)


@dataclass
class RetrievalContext:
    """Live clients a strategy needs. Owned and closed by the runner."""

    index: BaseIndex
    embedder: Any
    reranker: Any
    llm: Any


_HYDE_SYSTEM = (
    "You write a short, factual passage that would plausibly appear in an internal "
    "company document and that directly answers the user's question. Invent concrete "
    "specifics (numbers, names, thresholds) where needed. Do not hedge, do not mention "
    "that you are speculating, and do not address the reader. Output the passage only."
)

_MULTIQUERY_SYSTEM = (
    "You rewrite a search query into alternative phrasings for a document retrieval "
    "system. Vary vocabulary and specificity; keep every rewrite answerable by the same "
    'document. Respond with JSON: {"queries": ["...", "..."]}'
)


class Strategy:
    """A named, configured retrieval pipeline."""

    def __init__(
        self,
        name: str,
        config: PipelineConfig,
        *,
        label: str = "",
        description: str = "",
    ) -> None:
        config.validate()
        self.name = name
        self.config = config
        self.label = label or name
        self.description = description

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Strategy(name={self.name!r}, config={self.config.as_dict()})"

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "label": self.label, **self.config.as_dict()}

    # ------------------------------------------------------------- transform
    async def _expand_queries(
        self, question: str, ctx: RetrievalContext, usage: Usage
    ) -> tuple[list[str], list[str]]:
        """Return ``(dense_queries, lexical_queries)`` after transformation."""
        mode = self.config.query_transform
        if mode == "none":
            return [question], [question]

        if mode == "hyde":
            response = await ctx.llm.chat(
                [
                    {"role": "system", "content": _HYDE_SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"Question: {question}\n\n"
                            f"Write at most {self.config.hyde_max_words} words."
                        ),
                    },
                ],
                max_tokens=400,
            )
            usage.llm_calls += 1
            usage.prompt_tokens += response.prompt_tokens
            usage.completion_tokens += response.completion_tokens
            usage.cached_prompt_tokens += response.cached_prompt_tokens
            hypothetical = response.text.strip()
            # Keep the real question in the dense query set: a bad hallucinated
            # passage should degrade the run, not destroy it.
            dense = [hypothetical, question] if hypothetical else [question]
            return dense, [question]

        # multiquery
        response = await ctx.llm.chat(
            [
                {"role": "system", "content": _MULTIQUERY_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Query: {question}\n\n"
                        f"Produce exactly {self.config.multiquery_n} rewrites."
                    ),
                },
            ],
            max_tokens=400,
            json_mode=True,
        )
        usage.llm_calls += 1
        usage.prompt_tokens += response.prompt_tokens
        usage.completion_tokens += response.completion_tokens
        usage.cached_prompt_tokens += response.cached_prompt_tokens
        try:
            payload = extract_json_object(response.text)
            rewrites = [str(q).strip() for q in payload.get("queries", []) if str(q).strip()]
        except ValueError:
            rewrites = []
        queries = [question, *rewrites[: self.config.multiquery_n]]
        return queries, queries

    # -------------------------------------------------------------- retrieve
    async def retrieve(self, question: str, ctx: RetrievalContext) -> RetrievalOutcome:
        cfg = self.config
        usage = Usage()

        with Timer() as transform_timer:
            dense_queries, lexical_queries = await self._expand_queries(question, ctx, usage)
        expanded = sorted({*dense_queries, *lexical_queries} - {question})

        ranked_lists: list[list[tuple[int, float]]] = []
        weights: list[float] = []
        dense_scores: dict[int, float] = {}
        lexical_scores: dict[int, float] = {}
        embed_query_ms = 0.0

        with Timer() as retrieve_timer:
            if cfg.retriever in {"dense", "hybrid"}:
                with Timer() as embed_timer:
                    embedded = await ctx.embedder.embed(dense_queries, input_type="query")
                embed_query_ms = embed_timer.ms
                usage.embed_calls += 1
                usage.embed_tokens += embedded.tokens
                for row in range(embedded.vectors.shape[0]):
                    hits = await ctx.index.search_dense(embedded.vectors[row], cfg.candidate_k)
                    if hits:
                        ranked_lists.append(hits)
                        weights.append(cfg.dense_weight)
                        for pos, score in hits:
                            dense_scores[pos] = max(dense_scores.get(pos, -1.0), score)

            if cfg.retriever in {"lexical", "hybrid"}:
                for query in lexical_queries:
                    hits = ctx.index.search_lexical(query, cfg.candidate_k)
                    if hits:
                        ranked_lists.append(hits)
                        weights.append(cfg.lexical_weight)
                        for pos, score in hits:
                            lexical_scores[pos] = max(lexical_scores.get(pos, -1.0), score)

            if not ranked_lists:
                fused: list[tuple[int, float]] = []
            elif len(ranked_lists) == 1 and cfg.retriever != "hybrid":
                fused = list(ranked_lists[0])
            elif cfg.fusion == "weighted":
                fused = weighted_score_fusion(ranked_lists, weights=weights)
            else:
                fused = reciprocal_rank_fusion(ranked_lists, weights=weights)

            if cfg.max_per_doc > 0:
                fused = dedupe_by_document(
                    fused,
                    lambda pos: ctx.index.chunk_at(pos).doc_id,
                    max_per_doc=cfg.max_per_doc,
                )
            candidates = fused[: cfg.candidate_k]

        rerank_ms = 0.0
        rerank_scores: dict[int, float] = {}
        if cfg.rerank and candidates:
            with Timer() as rerank_timer:
                documents = [ctx.index.chunk_at(pos).text for pos, _ in candidates]
                result = await ctx.reranker.rerank(question, documents, top_k=cfg.top_k)
            rerank_ms = rerank_timer.ms
            usage.rerank_calls += 1
            usage.rerank_tokens += result.tokens or (
                estimate_tokens(question) * len(documents)
                + sum(estimate_tokens(d) for d in documents)
            )
            reordered: list[tuple[int, float]] = []
            for local_idx, score in result.ranking:
                if 0 <= local_idx < len(candidates):
                    position = candidates[local_idx][0]
                    rerank_scores[position] = score
                    reordered.append((position, score))
            final = reordered[: cfg.top_k]
        else:
            final = candidates[: cfg.top_k]

        chunks: list[RetrievedChunk] = []
        for rank, (position, score) in enumerate(final, start=1):
            chunk = ctx.index.chunk_at(position)
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    doc_id=chunk.doc_id,
                    text=chunk.generation_text,
                    title=chunk.title,
                    rank=rank,
                    score=float(score),
                    dense_score=dense_scores.get(position),
                    lexical_score=lexical_scores.get(position),
                    fused_score=next((s for p, s in candidates if p == position), None),
                    rerank_score=rerank_scores.get(position),
                )
            )

        return RetrievalOutcome(
            chunks=chunks,
            usage=usage,
            embed_query_ms=embed_query_ms,
            retrieve_ms=retrieve_timer.ms,
            rerank_ms=rerank_ms,
            transform_ms=transform_timer.ms,
            expanded_queries=expanded,
        )


def chunk_similarity_fn(index: BaseIndex, matrix: np.ndarray | None):
    """Similarity callable for MMR over an in-memory index."""

    def similarity(a: int, b: int) -> float:
        if matrix is None:
            return 0.0
        return float(np.dot(matrix[a], matrix[b]))

    return similarity
