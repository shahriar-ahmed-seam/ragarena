"""Benchmark orchestration.

One run = one dataset x N strategies. For every strategy the runner builds (or
reuses) an index, sends every question through the pipeline with bounded
concurrency, scores the result, and aggregates into a comparable row.

Two design choices worth knowing about:

* **Indexes are shared across strategies with identical chunking.** Embedding
  the corpus once per distinct chunker keeps a seven-strategy run cheap and
  removes ingest variance from the comparison.
* **Serving cost and evaluation cost are tracked separately.** The judge is
  usually the most expensive model in the run, and folding its bill into
  "cost per 1k queries" would make every strategy look identical and wrong.
"""

from __future__ import annotations

import asyncio
import platform
import sys
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from . import _version
from .cache import ResponseCache
from .chunking import Chunker
from .config import Settings
from .cost import compute_cost
from .datasets import dataset_info
from .generation import Generator
from .index import build_index
from .index.base import BaseIndex
from .metrics import Judge, retrieval_scores, summarise
from .metrics.aggregate import latency_stats, stage_latency
from .presets import default_chunker
from .providers import build_embedder, build_llm, build_reranker
from .strategies import RetrievalContext, Strategy
from .types import (
    Dataset,
    QueryTrace,
    Question,
    RunEnvironment,
    RunResult,
    StrategyResult,
    Timings,
    Usage,
)
from .utils import Timer, gather_limited, stable_hash

ProgressHook = Callable[[str, int, int], None]


@dataclass
class StrategySpec:
    """A strategy plus the chunker its index should be built with."""

    strategy: Strategy
    chunker: Chunker | None = None


class BenchmarkRunner:
    def __init__(
        self,
        settings: Settings,
        dataset: Dataset,
        specs: Sequence[StrategySpec] | Sequence[Strategy],
        *,
        index_backend: str = "memory",
        judge_enabled: bool = True,
        limit_questions: int | None = None,
        primary_metric: str = "",
        notes: str = "",
        on_progress: ProgressHook | None = None,
        on_strategy_start: Callable[[str, int, int], None] | None = None,
    ) -> None:
        self.settings = settings
        self.dataset = dataset
        self.specs: list[StrategySpec] = [
            spec if isinstance(spec, StrategySpec) else StrategySpec(strategy=spec)
            for spec in specs
        ]
        self.index_backend = index_backend
        self.judge_enabled = judge_enabled
        self.primary_metric = primary_metric or (
            "arena_score" if judge_enabled else "context_precision"
        )
        self.notes = notes
        self.on_progress = on_progress
        self.on_strategy_start = on_strategy_start
        self.questions: list[Question] = (
            dataset.questions[:limit_questions] if limit_questions else list(dataset.questions)
        )
        self.run_id = f"{dataset.name}-{uuid.uuid4().hex[:8]}"

        self.cache = ResponseCache(settings.cache_dir, enabled=settings.cache_enabled)
        self.llm = build_llm(settings, self.cache)
        self.embedder = build_embedder(settings, self.cache)
        self.reranker = build_reranker(settings, self.cache)
        self.generator = Generator(
            self.llm,
            model=settings.generator_model,
            temperature=settings.generator_temperature,
        )
        self.judge = Judge(
            self.llm, model=settings.judge_model, temperature=settings.judge_temperature
        )
        self._indexes: dict[str, BaseIndex] = {}
        # Report and bill the models that actually ran. `settings.embed_model`
        # can name a hosted model while the provider falls back to a local one,
        # and charging Voyage prices for CPU inference would be a lie.
        self.embed_model = getattr(self.embedder, "model", settings.embed_model)
        self.rerank_model = getattr(self.reranker, "model", settings.rerank_model)

    # ------------------------------------------------------------------ index
    async def _index_for(self, chunker: Chunker | None) -> BaseIndex:
        active = chunker or default_chunker()
        key = stable_hash({"chunker": active.config(), "embed": self.settings.embed_model})
        cached = self._indexes.get(key)
        if cached is not None:
            return cached

        chunks = active.chunk_all(self.dataset.documents)
        index = build_index(
            self.index_backend,
            self.embedder,
            database_url=self.settings.database_url,
            run_id=f"{self.run_id}-{key[:8]}",
        )
        await index.build(chunks)
        self._indexes[key] = index
        return index

    # ------------------------------------------------------------------ query
    async def _run_question(
        self, strategy: Strategy, ctx: RetrievalContext, question: Question
    ) -> QueryTrace:
        trace = QueryTrace(
            question_id=question.id,
            question=question.question,
            answerable=question.answerable,
            ground_truth=question.ground_truth,
        )
        try:
            with Timer() as total:
                outcome = await strategy.retrieve(question.question, ctx)
                generated = await self.generator.generate(question.question, outcome.chunks)

            pipeline_usage = outcome.usage + generated.usage
            trace.retrieved = outcome.chunks
            trace.answer = generated.answer
            trace.cached = generated.cached
            trace.timings = Timings(
                embed_query_ms=round(outcome.embed_query_ms, 2),
                retrieve_ms=round(outcome.retrieve_ms + outcome.transform_ms, 2),
                rerank_ms=round(outcome.rerank_ms, 2),
                generate_ms=round(
                    max(0.0, total.ms - outcome.retrieve_ms - outcome.transform_ms - outcome.rerank_ms),
                    2,
                ),
                total_ms=round(total.ms, 2),
            )
            trace.usage = pipeline_usage
            trace.cost = compute_cost(
                pipeline_usage,
                llm_model=self.settings.generator_model,
                embed_model=self.embed_model,
                rerank_model=self.rerank_model,
            )
            trace.scores = retrieval_scores(outcome.chunks, question, generated.answer)

            if self.judge_enabled:
                judged = await self.judge.evaluate(question, generated.answer, outcome.chunks)
                trace.scores.update(judged.scores)
                trace.judge_notes = judged.notes
                # Stash judge usage on the trace so the strategy total can add
                # it up without a second pass over the data.
                trace.judge_notes["_eval_usage"] = judged.usage.model_dump_json()
        except Exception as exc:
            trace.error = f"{type(exc).__name__}: {exc}"
        return trace

    # -------------------------------------------------------------- strategy
    async def _run_strategy(self, spec: StrategySpec) -> StrategyResult:
        strategy = spec.strategy
        index = await self._index_for(spec.chunker)
        ctx = RetrievalContext(
            index=index, embedder=self.embedder, reranker=self.reranker, llm=self.llm
        )

        def progress(done: int, total: int) -> None:
            if self.on_progress:
                self.on_progress(strategy.name, done, total)

        traces = await gather_limited(
            self.questions,
            lambda q: self._run_question(strategy, ctx, q),
            limit=self.settings.concurrency,
            on_done=progress,
        )

        metrics, segments = summarise(traces, self.questions)

        pipeline_usage = Usage()
        eval_usage = Usage()
        for trace in traces:
            pipeline_usage = pipeline_usage + trace.usage
            raw = trace.judge_notes.pop("_eval_usage", None)
            if raw:
                eval_usage = eval_usage + Usage.model_validate_json(raw)

        cost = compute_cost(
            pipeline_usage,
            llm_model=self.settings.generator_model,
            embed_model=self.embed_model,
            rerank_model=self.rerank_model,
        )
        cost_uncached = compute_cost(
            pipeline_usage,
            llm_model=self.settings.generator_model,
            embed_model=self.embed_model,
            rerank_model=self.rerank_model,
            ignore_prompt_cache=True,
        )
        eval_cost = compute_cost(
            eval_usage,
            llm_model=self.settings.judge_model,
            embed_model="none",
            rerank_model="none",
        )
        answered = max(1, len([t for t in traces if t.error is None]))

        chunker_config = (spec.chunker or default_chunker()).config()
        return StrategyResult(
            name=strategy.name,
            label=strategy.label,
            description=strategy.description,
            config={**strategy.config.as_dict(), **chunker_config, "index": index.name},
            metrics=metrics,
            metrics_by_segment=segments,
            latency=latency_stats(traces),
            stage_latency=stage_latency(traces),
            usage=pipeline_usage,
            cost=cost,
            cost_per_1k_queries_usd=round(cost.total_usd / answered * 1000, 4),
            cost_per_1k_queries_uncached_usd=round(cost_uncached.total_usd / answered * 1000, 4),
            eval_usage=eval_usage,
            eval_cost_usd=round(eval_cost.total_usd, 6),
            index_build_ms=round(index.build_ms, 2),
            n_chunks=index.size,
            n_questions=len(traces),
            n_errors=len([t for t in traces if t.error]),
            traces=traces,
        )

    # ------------------------------------------------------------------- run
    async def run(self) -> RunResult:
        results: list[StrategyResult] = []
        try:
            with Timer() as total:
                for position, spec in enumerate(self.specs, start=1):
                    if self.on_strategy_start:
                        self.on_strategy_start(spec.strategy.name, position, len(self.specs))
                    results.append(await self._run_strategy(spec))
        finally:
            await self.aclose()

        return RunResult(
            run_id=self.run_id,
            duration_s=round(total.ms / 1000, 2),
            dataset=dataset_info(self.dataset),
            environment=RunEnvironment(
                ragarena_version=_version.__version__,
                python_version=sys.version.split()[0],
                platform=platform.platform(),
                concurrency=self.settings.concurrency,
                index_backend=self.index_backend,
                generator_model=self.settings.generator_model,
                judge_model=self.settings.judge_model if self.judge_enabled else "none",
                embed_provider=getattr(self.embedder, "name", self.settings.embed_provider),
                embed_model=self.embed_model,
                rerank_provider=getattr(self.reranker, "name", self.settings.rerank_provider),
                rerank_model=self.rerank_model,
            ),
            strategies=results,
            primary_metric=self.primary_metric,
            notes=self.notes,
        )

    async def aclose(self) -> None:
        for index in self._indexes.values():
            await index.aclose()
        await asyncio.gather(
            self.llm.aclose(),
            self.embedder.aclose(),
            self.reranker.aclose(),
            return_exceptions=True,
        )
        self.cache.close()
