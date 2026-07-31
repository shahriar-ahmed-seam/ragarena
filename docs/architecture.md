# Architecture

## Module map

```
src/ragarena/
  types.py          Pydantic data model. Everything crossing a module boundary is one of these.
  config.py         Settings, resolved from kwargs > env > .env > defaults.
  errors.py         Exception hierarchy.
  cost.py           Provider price tables and USD accounting.
  cache.py          SQLite response cache, keyed by exact request payload.
  utils.py          Timing, percentiles, hashing, text normalisation, bounded async gather.

  providers/
    base.py         Protocols, shared httpx client, retry/backoff, rate limiter.
    llm.py          Any OpenAI-compatible /chat/completions endpoint.
    embeddings.py   Voyage AI (hosted), fastembed (local ONNX), hash (offline stub).
    rerankers.py    Voyage AI, local cross-encoder, no-op.
    __init__.py     build_llm / build_embedder / build_reranker from Settings.

  chunking.py       fixed, recursive, markdown-section, sentence-window.
  index/
    base.py         Index protocol: dense leg + lexical leg.
    bm25.py         Okapi BM25, in-package.
    memory.py       Exact numpy dense search + BM25.
    pgvector.py     Postgres HNSW + tsvector full text.
  fusion.py         RRF, weighted score fusion, MMR, per-document capping.

  strategies.py     PipelineConfig and the single configurable retrieval pipeline.
  presets.py        Named strategies and the benchmark suites.
  generation.py     Cited answer synthesis with explicit abstention.

  metrics/
    retrieval.py    Deterministic metrics.
    judged.py       LLM-as-judge grounding and answer quality.
    aggregate.py    Per-strategy aggregation, arena_score, latency percentiles, segments.

  datasets/
    __init__.py     Loader and label validator.
    meridian/       Bundled synthetic corpus + labelled questions.

  runner.py         Orchestration: index reuse, bounded concurrency, cost split.
  report/           HTML report (Jinja2) and JSON artefacts for the site.
  cli.py            Typer CLI.

site/               Next.js leaderboard, reads results/*.summary.json at build time.
results/            Committed run artefacts.
```

## Request path for one benchmarked question

```
BenchmarkRunner._run_question
  |
  +-- Strategy.retrieve
  |     +-- _expand_queries          LLM call, only for hyde / multiquery
  |     +-- embedder.embed(query)    hosted or local, cached
  |     +-- index.search_dense       exact cosine, or pgvector HNSW
  |     +-- index.search_lexical     BM25, or Postgres ts_rank_cd
  |     +-- fusion                   RRF or weighted, then optional per-doc cap
  |     +-- reranker.rerank          cross-encoder over candidate_k, keeps top_k
  |
  +-- Generator.generate             cited answer, or the abstention token
  |
  +-- metrics.retrieval_scores       deterministic, free
  +-- metrics.Judge.evaluate         two LLM calls: grounding, then quality
  |
  +-- QueryTrace                     retrieved chunks, answer, scores, usage, cost, timings
```

Aggregation turns the traces into one `StrategyResult`, and the run collects those into a `RunResult` that serialises losslessly to JSON.

## Decisions and why

**Strategies are configuration, not subclasses.** A class per technique multiplies out: hybrid × rerank × HyDE is three concepts and eight classes. One `PipelineConfig` keeps the axes orthogonal and makes a parameter sweep a list comprehension.

**Indexes are shared across strategies with identical chunking.** Keyed by a hash of `(chunker config, embedding model)`. A seven-strategy run embeds the corpus once instead of seven times, and ingest variance stops leaking into the strategy comparison.

**Exact dense search is the default.** ANN recall is a confounder: a strategy comparison run over an untuned HNSW index measures the index. At benchmark corpus sizes a single matrix multiply is also faster than building a graph. `--index pgvector` exists for when you want to measure the production path on purpose.

**Serving cost and evaluation cost are separate fields.** The judge is usually the most expensive model in the run. Folding its bill into cost-per-query would swamp the differences between strategies with a constant.

**Prompt-cache-independent cost is reported alongside the real one.** DeepSeek bills cached prompt prefixes at roughly 2% of the miss rate, so the second run over a corpus looks cheaper than the first. The leaderboard ranks on the uncached figure so run order cannot change the conclusion.

**Everything is cached, and cache hits are excluded from latency.** Provider calls dominate wall-clock and cost; caching them keyed on the exact request payload makes iteration practical. But a cached run measures SQLite, so `latency_stats` filters cache hits out and only falls back to including them if there is nothing else.

**One bad question cannot kill a run.** `_run_question` catches per-question exceptions onto `QueryTrace.error`, so a provider hiccup on question 40 of 78 costs you one data point instead of fourteen minutes.

**Rate limiting is client-side and explicit.** Free provider tiers can be 3 requests/minute. Discovering that through a wall of 429s wastes a run, so `--voyage-rpm` / `--llm-rpm` pace the client and the limiter serialises across concurrent tasks.

**The judge disables thinking mode.** DeepSeek V4 enables chain-of-thought by default. For grading, that costs latency and tokens and adds score variance between runs, so `thinking: disabled` plus `temperature: 0` is set explicitly.

## Extension points

| I want to... | Do this |
| --- | --- |
| Add a provider | Implement the `LLMProvider` / `EmbeddingProvider` / `RerankProvider` protocol in `providers/`, register it in `providers/__init__.py`. |
| Add a chunker | Subclass `Chunker`, add it to the `CHUNKERS` registry in `chunking.py`. |
| Add an index backend | Subclass `BaseIndex` (dense leg + lexical leg), register in `index/__init__.py`. |
| Add a metric | Add a function to `metrics/retrieval.py` and include it in `retrieval_scores`, or add a judge prompt in `metrics/judged.py`. |
| Change the headline weighting | Edit `ARENA_WEIGHTS` in `metrics/aggregate.py`. |
| Add a strategy | Construct a `Strategy` with a `PipelineConfig`, or add an entry to `PRESETS`. |

## Leaderboard site

The site is a static Next.js app. At build time it reads `results/index.json` and each `*.summary.json`, so there is no server, no database and no API keys in the deployment. Publishing a new benchmark is a commit:

```bash
ragarena bench --suite default --out results
git add results && git commit -m "bench: new run" && git push
```

Summary payloads carry aggregate metrics for every strategy but per-question traces only for the winner, which keeps the page fast while leaving the winning answers inspectable.
