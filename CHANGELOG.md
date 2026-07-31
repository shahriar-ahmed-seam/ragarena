# Changelog

All notable changes to RAGArena. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-07-31

First release.

### Added

- **Benchmark runner** — one dataset × N strategies, bounded concurrency, per-question error isolation, indexes shared across strategies with identical chunking.
- **Strategies as configuration** — `PipelineConfig` covers retriever (dense / lexical / hybrid), query transform (none / HyDE / multi-query), fusion (RRF / weighted score), reranking, candidate pool depth and per-document capping. Eight named presets and three suites (`default`, `quick`, `chunking`).
- **Chunkers** — fixed word window, recursive character, markdown-section, sentence-window (separate retrieval and generation text).
- **Index backends** — exact numpy dense search plus in-package Okapi BM25; Postgres/pgvector with HNSW and `ts_rank_cd` full text.
- **Providers** — any OpenAI-compatible chat endpoint (verified against DeepSeek V4), Voyage AI embeddings and rerankers, local CPU embeddings and cross-encoder via fastembed, and a deterministic offline hash embedder for CI.
- **Metrics** — deterministic: hit rate, precision@k, document recall, MRR, nDCG@k, context precision, citation validity, citation coverage, abstention accuracy, hallucination rate. LLM-judged: claim-level faithfulness, answer relevance, answer correctness. Composite `arena_score`.
- **Cost accounting** — real token counts against published prices, split three ways: serving cost, prompt-cache-independent serving cost, and evaluation cost.
- **Latency** — end-to-end and per-stage percentiles with cache hits excluded and run concurrency recorded.
- **`meridian` dataset** — 20 original synthetic documents (7,088 words) and 78 labelled questions including 11 unanswerable traps, cross-document multi-hop questions and deliberate near-identical distractors.
- **Response cache** — SQLite, keyed on the exact request payload, making re-runs fast and free.
- **Client-side rate limiting** — `--voyage-rpm` / `--llm-rpm` for free provider tiers that cap at a few requests per minute.
- **CLI** — `bench`, `ask`, `report`, `validate`, `doctor`, `strategies`, `datasets`, `cache`.
- **Artefacts** — full run JSON, a self-contained offline HTML report, and compact summaries plus an index consumed by the static leaderboard site.
- **Leaderboard site** — Next.js static export, builds from committed JSON with no server or credentials.
- **Packaging** — Docker image running non-root, docker-compose with pgvector, Makefile, GitHub Actions CI across Python 3.10–3.13, PyPI publish workflow via Trusted Publishing.

### Notes

- `deepseek-chat` and `deepseek-reasoner` were discontinued on 2026-07-24. Defaults are `deepseek-v4-flash` for generation and `deepseek-v4-pro` for judging, both with thinking mode explicitly disabled so benchmark scores stay stable and cheap.
