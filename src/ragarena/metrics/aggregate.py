"""Aggregation: per-question traces -> one comparable row per strategy."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from ..types import LatencyStats, QueryTrace, Question
from ..utils import mean, percentile

# Headline number for the leaderboard. Weights encode a product opinion:
# a wrong-but-confident answer is the worst outcome, so grounding and
# correctness dominate, and citation quality still counts because a RAG product
# that cites the wrong source is broken even when the prose is right.
ARENA_WEIGHTS: dict[str, float] = {
    "faithfulness": 0.35,
    "answer_correctness": 0.25,
    "context_precision": 0.20,
    "citation_validity": 0.10,
    "abstention_correct": 0.10,
}

# Order used by the report and the site.
METRIC_ORDER = [
    "arena_score",
    "faithfulness",
    "answer_correctness",
    "answer_relevance",
    "context_precision",
    "hit_rate",
    "doc_recall",
    "precision@k",
    "mrr",
    "ndcg@k",
    "citation_validity",
    "citation_coverage",
    "abstention_correct",
    "hallucination_rate",
]

HIGHER_IS_BETTER = dict.fromkeys(METRIC_ORDER, True)
HIGHER_IS_BETTER["hallucination_rate"] = False


def average_scores(traces: Sequence[QueryTrace]) -> dict[str, float]:
    """Mean of each metric over the traces that actually reported it.

    Metrics are skipped rather than zero-filled when a question type does not
    define them, so the unanswerable subset cannot silently deflate retrieval
    averages.
    """
    buckets: dict[str, list[float]] = defaultdict(list)
    for trace in traces:
        for key, value in trace.scores.items():
            buckets[key].append(value)
    return {key: round(mean(values), 4) for key, values in sorted(buckets.items())}


def arena_score(metrics: dict[str, float]) -> float:
    """Weighted composite over the metrics that are present."""
    total_weight = 0.0
    total = 0.0
    for key, weight in ARENA_WEIGHTS.items():
        if key in metrics:
            total += metrics[key] * weight
            total_weight += weight
    return round(total / total_weight, 4) if total_weight else 0.0


def latency_stats(traces: Sequence[QueryTrace], *, cold_only: bool = True) -> LatencyStats:
    """Percentiles over end-to-end query latency.

    Cache hits are excluded by default: a cached run measures SQLite, not the
    pipeline. Falls back to all traces if everything was cached.
    """
    values = [t.timings.total_ms for t in traces if t.error is None and (not cold_only or not t.cached)]
    if not values:
        values = [t.timings.total_ms for t in traces if t.error is None]
    if not values:
        return LatencyStats()
    return LatencyStats(
        mean_ms=round(mean(values), 2),
        p50_ms=round(percentile(values, 50), 2),
        p90_ms=round(percentile(values, 90), 2),
        p95_ms=round(percentile(values, 95), 2),
        p99_ms=round(percentile(values, 99), 2),
        max_ms=round(max(values), 2),
    )


def stage_latency(traces: Sequence[QueryTrace], *, cold_only: bool = True) -> dict[str, float]:
    """Mean milliseconds per pipeline stage, to show where the time goes."""
    pool = [t for t in traces if t.error is None and (not cold_only or not t.cached)]
    if not pool:
        pool = [t for t in traces if t.error is None]
    if not pool:
        return {}
    return {
        "embed_query_ms": round(mean(t.timings.embed_query_ms for t in pool), 2),
        "retrieve_ms": round(mean(t.timings.retrieve_ms for t in pool), 2),
        "rerank_ms": round(mean(t.timings.rerank_ms for t in pool), 2),
        "generate_ms": round(mean(t.timings.generate_ms for t in pool), 2),
    }


def segment_scores(
    traces: Sequence[QueryTrace], questions: Sequence[Question]
) -> dict[str, dict[str, float]]:
    """Break metrics down by difficulty, question type and answerability."""
    by_id = {q.id: q for q in questions}
    groups: dict[str, list[QueryTrace]] = defaultdict(list)
    for trace in traces:
        question = by_id.get(trace.question_id)
        if question is None:
            continue
        groups[f"difficulty:{question.difficulty.value}"].append(trace)
        groups[f"type:{question.type.value}"].append(trace)
        groups["answerable" if question.answerable else "unanswerable"].append(trace)

    out: dict[str, dict[str, float]] = {}
    for label, bucket in sorted(groups.items()):
        scores = average_scores(bucket)
        scores["n"] = float(len(bucket))
        if "faithfulness" in scores:
            scores["arena_score"] = arena_score(scores)
        out[label] = scores
    return out


def summarise(
    traces: Sequence[QueryTrace], questions: Sequence[Question]
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    metrics = average_scores(traces)
    # The composite is only meaningful with the judged metrics present. With
    # --no-judge it would be a weighted average of three retrieval metrics
    # dressed up as an answer-quality score, so it is omitted instead.
    if "faithfulness" in metrics:
        metrics["arena_score"] = arena_score(metrics)
    ordered = {k: metrics[k] for k in METRIC_ORDER if k in metrics}
    ordered.update({k: v for k, v in metrics.items() if k not in ordered})
    return ordered, segment_scores(traces, questions)
