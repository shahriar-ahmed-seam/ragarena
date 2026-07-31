"""Metrics: deterministic retrieval scores plus LLM-judged answer quality."""

from __future__ import annotations

from .aggregate import (
    ARENA_WEIGHTS,
    HIGHER_IS_BETTER,
    METRIC_ORDER,
    arena_score,
    average_scores,
    latency_stats,
    segment_scores,
    stage_latency,
    summarise,
)
from .judged import Judge, JudgeOutcome
from .retrieval import (
    abstention_correct,
    citation_coverage,
    citation_validity,
    context_precision,
    document_recall,
    hit_rate,
    is_relevant,
    mrr,
    ndcg_at_k,
    precision_at_k,
    retrieval_scores,
)

__all__ = [
    "ARENA_WEIGHTS",
    "HIGHER_IS_BETTER",
    "METRIC_ORDER",
    "Judge",
    "JudgeOutcome",
    "abstention_correct",
    "arena_score",
    "average_scores",
    "citation_coverage",
    "citation_validity",
    "context_precision",
    "document_recall",
    "hit_rate",
    "is_relevant",
    "latency_stats",
    "mrr",
    "ndcg_at_k",
    "precision_at_k",
    "retrieval_scores",
    "segment_scores",
    "stage_latency",
    "summarise",
]
