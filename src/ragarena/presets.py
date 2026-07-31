"""Named strategy presets.

The default suite walks up the complexity ladder one change at a time, so each
row of the leaderboard isolates the effect of exactly one decision:

    bm25-only          lexical baseline
    dense-only         is the embedding model pulling its weight?
    hybrid-rrf         does fusing lexical + dense beat either alone?
    hybrid-rerank      what does a cross-encoder add on top of fusion?
    hybrid-rerank-wide does a bigger candidate pool help the reranker?
    multiquery-rerank  does query expansion beat a wider pool?
    hyde-rerank        does a hypothetical document beat the raw query?
"""

from __future__ import annotations

from .chunking import Chunker, get_chunker
from .errors import StrategyError
from .strategies import PipelineConfig, Strategy

PRESETS: dict[str, dict[str, object]] = {
    "bm25-only": {
        "label": "BM25 only",
        "description": "Pure lexical retrieval. No embeddings, no LLM calls before generation.",
        "config": PipelineConfig(retriever="lexical", top_k=5, candidate_k=20),
    },
    "dense-only": {
        "label": "Dense only",
        "description": "Single-vector cosine search over the whole corpus.",
        "config": PipelineConfig(retriever="dense", top_k=5, candidate_k=20),
    },
    "hybrid-rrf": {
        "label": "Hybrid + RRF",
        "description": "BM25 and dense results fused with Reciprocal Rank Fusion.",
        "config": PipelineConfig(retriever="hybrid", fusion="rrf", top_k=5, candidate_k=20),
    },
    "hybrid-weighted": {
        "label": "Hybrid + weighted fusion",
        "description": "Min-max normalised score fusion instead of rank fusion.",
        "config": PipelineConfig(retriever="hybrid", fusion="weighted", top_k=5, candidate_k=20),
    },
    "hybrid-rerank": {
        "label": "Hybrid + rerank",
        "description": "Fuse 20 candidates, then a cross-encoder picks the final 5.",
        "config": PipelineConfig(retriever="hybrid", rerank=True, top_k=5, candidate_k=20),
    },
    "hybrid-rerank-wide": {
        "label": "Hybrid + rerank (wide)",
        "description": "Same as hybrid + rerank but with a 40-candidate pool.",
        "config": PipelineConfig(retriever="hybrid", rerank=True, top_k=5, candidate_k=40),
    },
    "multiquery-rerank": {
        "label": "Multi-query + rerank",
        "description": "LLM writes 3 query rewrites, all results fused, then reranked.",
        "config": PipelineConfig(
            retriever="hybrid",
            query_transform="multiquery",
            rerank=True,
            top_k=5,
            candidate_k=30,
            multiquery_n=3,
        ),
    },
    "hyde-rerank": {
        "label": "HyDE + rerank",
        "description": "LLM drafts a hypothetical answer passage, used as the dense query.",
        "config": PipelineConfig(
            retriever="hybrid",
            query_transform="hyde",
            rerank=True,
            top_k=5,
            candidate_k=30,
        ),
    },
}

DEFAULT_SUITE = [
    "bm25-only",
    "dense-only",
    "hybrid-rrf",
    "hybrid-rerank",
    "hybrid-rerank-wide",
    "multiquery-rerank",
    "hyde-rerank",
]

QUICK_SUITE = ["bm25-only", "dense-only", "hybrid-rrf", "hybrid-rerank"]

# Chunker used for every preset unless overridden, so strategy comparisons are
# not silently confounded by a chunking change.
DEFAULT_CHUNKER = ("markdown-section", {"max_chars": 1400, "overlap_chars": 120})

# Chunking sweep: identical retrieval, different chunkers. Answers "is my
# chunking the bottleneck?" which is usually the first thing to check.
CHUNKING_SUITE: dict[str, tuple[str, dict[str, object]]] = {
    "chunk-fixed-180": ("fixed", {"size_words": 180, "overlap_words": 30}),
    "chunk-recursive-1100": ("recursive", {"size_chars": 1100, "overlap_chars": 150}),
    "chunk-markdown": ("markdown-section", {"max_chars": 1400, "overlap_chars": 120}),
    "chunk-sentence-window": ("sentence-window", {"sentences_per_chunk": 2, "window": 3}),
}


def get_preset(name: str) -> Strategy:
    """Build a :class:`Strategy` from a preset name."""
    try:
        spec = PRESETS[name]
    except KeyError as exc:
        raise StrategyError(
            f"Unknown preset {name!r}. Available: {', '.join(sorted(PRESETS))}"
        ) from exc
    config: PipelineConfig = spec["config"]  # type: ignore[assignment]
    return Strategy(
        name=name,
        config=PipelineConfig(**config.as_dict()),
        label=str(spec.get("label", name)),
        description=str(spec.get("description", "")),
    )


def build_suite(names: list[str] | None = None) -> list[Strategy]:
    return [get_preset(n) for n in (names or DEFAULT_SUITE)]


def default_chunker() -> Chunker:
    name, kwargs = DEFAULT_CHUNKER
    return get_chunker(name, **kwargs)


def chunking_suite() -> list[tuple[Strategy, Chunker]]:
    """Strategies for the chunking sweep: one retrieval config, many chunkers."""
    base = PRESETS["hybrid-rerank"]["config"]
    assert isinstance(base, PipelineConfig)
    out: list[tuple[Strategy, Chunker]] = []
    for name, (chunker_name, kwargs) in CHUNKING_SUITE.items():
        strategy = Strategy(
            name=name,
            config=PipelineConfig(**base.as_dict()),
            label=name.replace("chunk-", "").replace("-", " "),
            description=f"hybrid + rerank retrieval over {chunker_name} chunks",
        )
        out.append((strategy, get_chunker(chunker_name, **kwargs)))
    return out
