"""Core data model.

Everything that crosses a module boundary in RAGArena is one of these Pydantic
models, so a run can be serialised to JSON, diffed, committed to git and
rendered by the leaderboard site without any lossy conversion step.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #


class Document(Strict):
    """One source document in the corpus."""

    id: str
    text: str
    title: str = ""
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(Strict):
    """A retrievable unit produced by a chunking strategy."""

    id: str
    doc_id: str
    text: str
    ordinal: int = 0
    title: str = ""
    # Text handed to the generator. Usually identical to ``text``, but a
    # sentence-window strategy retrieves on a small window and generates from a
    # wider one, so the two are kept separate.
    context_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def generation_text(self) -> str:
        return self.context_text or self.text


# --------------------------------------------------------------------------- #
# Questions / dataset
# --------------------------------------------------------------------------- #


class QuestionType(str, Enum):
    FACTOID = "factoid"
    NUMERIC = "numeric"
    MULTI_HOP = "multi_hop"
    COMPARISON = "comparison"
    UNANSWERABLE = "unanswerable"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Question(Strict):
    """A graded question with the ground truth needed to score a pipeline."""

    id: str
    question: str
    ground_truth: str | None = None
    # Documents that actually contain the answer. Used for recall/precision.
    relevant_doc_ids: list[str] = Field(default_factory=list)
    # Optional: substrings that must appear in a retrieved chunk for it to
    # count as relevant. Enables chunk-level (not just doc-level) scoring.
    relevant_snippets: list[str] = Field(default_factory=list)
    answerable: bool = True
    type: QuestionType = QuestionType.FACTOID
    difficulty: Difficulty = Difficulty.MEDIUM
    tags: list[str] = Field(default_factory=list)


class Dataset(Strict):
    name: str
    description: str = ""
    version: str = "1"
    documents: list[Document] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)

    @property
    def n_documents(self) -> int:
        return len(self.documents)

    @property
    def n_questions(self) -> int:
        return len(self.questions)

    @property
    def total_words(self) -> int:
        return sum(len(d.text.split()) for d in self.documents)


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #


class RetrievedChunk(Strict):
    """A chunk returned by a retriever, with the score trail that produced it."""

    chunk_id: str
    doc_id: str
    text: str
    rank: int
    score: float
    dense_score: float | None = None
    lexical_score: float | None = None
    fused_score: float | None = None
    rerank_score: float | None = None
    title: str = ""

    def preview(self, n: int = 240) -> str:
        t = " ".join(self.text.split())
        return t if len(t) <= n else t[: n - 1] + "…"


# --------------------------------------------------------------------------- #
# Usage / cost / timing
# --------------------------------------------------------------------------- #


class Usage(Strict):
    """Token counters, split by the service that consumed them."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_prompt_tokens: int = 0
    embed_tokens: int = 0
    rerank_tokens: int = 0
    llm_calls: int = 0
    embed_calls: int = 0
    rerank_calls: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            cached_prompt_tokens=self.cached_prompt_tokens + other.cached_prompt_tokens,
            embed_tokens=self.embed_tokens + other.embed_tokens,
            rerank_tokens=self.rerank_tokens + other.rerank_tokens,
            llm_calls=self.llm_calls + other.llm_calls,
            embed_calls=self.embed_calls + other.embed_calls,
            rerank_calls=self.rerank_calls + other.rerank_calls,
        )


class Cost(Strict):
    """USD cost, derived from :class:`Usage` and a pricing table."""

    llm_usd: float = 0.0
    embed_usd: float = 0.0
    rerank_usd: float = 0.0

    @property
    def total_usd(self) -> float:
        return round(self.llm_usd + self.embed_usd + self.rerank_usd, 8)

    def __add__(self, other: Cost) -> Cost:
        return Cost(
            llm_usd=self.llm_usd + other.llm_usd,
            embed_usd=self.embed_usd + other.embed_usd,
            rerank_usd=self.rerank_usd + other.rerank_usd,
        )


class Timings(Strict):
    """Wall-clock milliseconds per pipeline stage."""

    embed_query_ms: float = 0.0
    retrieve_ms: float = 0.0
    rerank_ms: float = 0.0
    generate_ms: float = 0.0
    total_ms: float = 0.0


# --------------------------------------------------------------------------- #
# Answers and per-question traces
# --------------------------------------------------------------------------- #


class Answer(Strict):
    text: str
    # 1-based indices into the retrieved context that the generator cited.
    citations: list[int] = Field(default_factory=list)
    abstained: bool = False


class QueryTrace(Strict):
    """The full record of one question run through one strategy."""

    question_id: str
    question: str
    answerable: bool = True
    ground_truth: str | None = None
    retrieved: list[RetrievedChunk] = Field(default_factory=list)
    answer: Answer | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    judge_notes: dict[str, str] = Field(default_factory=dict)
    usage: Usage = Field(default_factory=Usage)
    cost: Cost = Field(default_factory=Cost)
    timings: Timings = Field(default_factory=Timings)
    error: str | None = None
    cached: bool = False


# --------------------------------------------------------------------------- #
# Aggregated results
# --------------------------------------------------------------------------- #


class LatencyStats(Strict):
    mean_ms: float = 0.0
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    max_ms: float = 0.0


class StrategyResult(Strict):
    """Aggregate outcome for a single named strategy over the whole dataset."""

    name: str
    label: str = ""
    description: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    metrics_by_segment: dict[str, dict[str, float]] = Field(default_factory=dict)
    latency: LatencyStats = Field(default_factory=LatencyStats)
    stage_latency: dict[str, float] = Field(default_factory=dict)
    usage: Usage = Field(default_factory=Usage)
    cost: Cost = Field(default_factory=Cost)
    cost_per_1k_queries_usd: float = 0.0
    # Same figure with every prompt token priced at the cache-miss rate. Use
    # this one to compare strategies or runs; provider-side prompt caching makes
    # the raw number depend on run order.
    cost_per_1k_queries_uncached_usd: float = 0.0
    # Cost of grading this strategy. Reported separately: it is the price of
    # measuring, not of serving, and must not pollute the cost comparison.
    eval_usage: Usage = Field(default_factory=Usage)
    eval_cost_usd: float = 0.0
    index_build_ms: float = 0.0
    n_chunks: int = 0
    n_questions: int = 0
    n_errors: int = 0
    traces: list[QueryTrace] = Field(default_factory=list)


class DatasetInfo(Strict):
    name: str
    description: str = ""
    version: str = "1"
    n_documents: int = 0
    n_questions: int = 0
    total_words: int = 0
    question_types: dict[str, int] = Field(default_factory=dict)


class RunEnvironment(Strict):
    ragarena_version: str
    python_version: str
    platform: str
    # Latency is measured under this level of parallelism. CPU-bound local
    # models contend with each other, so the number is needed to read a p95.
    concurrency: int = 1
    index_backend: str = "memory"
    generator_model: str
    judge_model: str
    embed_provider: str
    embed_model: str
    rerank_provider: str
    rerank_model: str


class RunResult(Strict):
    """Top-level artefact of `ragarena bench`: one JSON file per run."""

    run_id: str
    created_at: datetime = Field(default_factory=_utcnow)
    duration_s: float = 0.0
    dataset: DatasetInfo
    environment: RunEnvironment
    strategies: list[StrategyResult] = Field(default_factory=list)
    primary_metric: str = "faithfulness"
    notes: str = ""

    def leaderboard(self, metric: str | None = None) -> list[StrategyResult]:
        key = metric or self.primary_metric
        return sorted(
            self.strategies,
            key=lambda s: s.metrics.get(key, float("-inf")),
            reverse=True,
        )

    def best(self, metric: str | None = None) -> StrategyResult | None:
        board = self.leaderboard(metric)
        return board[0] if board else None
