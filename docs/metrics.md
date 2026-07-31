# Metrics

Every metric is computed per question and then averaged per strategy. Metrics that are undefined for a question type are **skipped**, not zero-filled: the unanswerable subset has no relevant documents, so including it in `hit_rate` would drag retrieval scores down for reasons that have nothing to do with retrieval.

## Deterministic metrics

No LLM involved. Free, reproducible, and the first place to look when a pipeline regresses.

Relevance is decided in two ways, in this order:

1. The chunk's document id appears in the question's `relevant_doc_ids`.
2. The chunk text contains one of the question's `relevant_snippets` (whitespace-, case- and punctuation-insensitive).

The second rule is what keeps relevance judgements stable when you change chunker, which is why the chunking sweep is meaningful rather than a comparison of coincidences.

| Metric | Definition |
| --- | --- |
| `hit_rate` | 1.0 if at least one retrieved chunk is relevant. |
| `precision@k` | Relevant chunks ÷ chunks returned. |
| `doc_recall` | Distinct labelled documents represented in the results ÷ labelled documents. |
| `mrr` | Reciprocal rank of the first relevant chunk. |
| `ndcg@k` | Binary-gain nDCG. Rewards ranking the relevant chunk first, not merely including it. |
| `context_precision` | Mean of precision@i over the positions holding a relevant chunk. Rank-sensitive: moving a relevant chunk up raises the score with the retrieved set unchanged. |
| `citation_validity` | Of the passages the answer cited, the share that were genuinely relevant. |
| `citation_coverage` | 1.0 when a non-abstaining answer cited at least one passage. |
| `abstention_correct` | 1.0 when the pipeline abstained exactly when it should have. Scored on answerable questions too, so a chronic refuser is penalised rather than rewarded. |
| `hallucination_rate` | Share of unanswerable questions that got an answer anyway. Lower is better; it is the only inverted metric. |

### Why `citation_validity` is separate

A pipeline can retrieve the right passage, write a correct answer, and cite the wrong number. Text-similarity metrics score that as a success. For a product that shows sources to users it is a defect, so it gets its own number.

## LLM-judged metrics

Two judge calls per answer, both at temperature 0 with thinking mode disabled, both cached.

### `faithfulness` — claim-level grounding

The judge splits the answer into atomic factual claims and labels each `supported` or `unsupported` against the retrieved context. The score is `supported ÷ total`.

Claim-level rather than a holistic 1-5 rating, because one fabricated sentence inside an otherwise correct answer is exactly the failure worth catching, and a holistic score averages it away. Numbers, names, dates and thresholds have to match exactly to count as supported — which matters on a corpus that deliberately contains six different retention windows.

The unsupported claims are stored on the trace and rendered in the HTML report, so a low score is always traceable to a specific sentence.

### `answer_relevance` and `answer_correctness`

A single judge call scores both on a 0-4 rubric, normalised to 0-1:

- **relevance**: 0 off-topic, 1 tangential, 2 partial, 3 minor gaps, 4 fully addresses the question.
- **correctness**: 0 contradicts the reference, 1 mostly wrong, 2 half right, 3 right with a minor omission, 4 fully matches.

The judge is instructed to grade substance and ignore formatting, length and citation markers, so a correct answer phrased differently from the reference still scores 4.

Unanswerable questions are not judged at all. The correct behaviour there is abstention, already measured deterministically, and asking a judge to grade a refusal against a null reference only adds noise.

## `arena_score`

The headline composite:

```
0.35 × faithfulness
0.25 × answer_correctness
0.20 × context_precision
0.10 × citation_validity
0.10 × abstention_correct
```

The weights are an opinion, and a defensible one: for a RAG product the worst outcome is a confident wrong answer, so grounding and correctness dominate; retrieval quality is the mechanism that produces them; citation and abstention behaviour are what make the product trustworthy rather than merely accurate.

Weights renormalise over whatever metrics are present. With `--no-judge` the composite is **omitted entirely** rather than silently recomputed from three retrieval metrics, and the leaderboard falls back to ranking on `context_precision`.

Override the weights by editing `ARENA_WEIGHTS` in `ragarena/metrics/aggregate.py`, or ignore the composite and rank on whichever single metric matches your product risk.

## Latency

Measured end to end per question and broken out per stage: `embed_query_ms`, `retrieve_ms` (including query transformation), `rerank_ms`, `generate_ms`.

Two things to know before quoting a p95:

- **Cache hits are excluded.** A cached run measures SQLite, not your pipeline. If every trace was cached the harness falls back to reporting all of them rather than reporting nothing.
- **Concurrency is recorded in the run artefact.** Local ONNX models saturate the CPU, so eight questions in flight contend with each other and inflate the tail. Compare latency only between strategies measured at the same concurrency, and use `--concurrency 1` if you want numbers that resemble single-user latency.

## Cost

Real token counts from the provider response multiplied by published per-million prices ([DeepSeek](https://api-docs.deepseek.com/quick_start/pricing), [Voyage AI](https://docs.voyageai.com/docs/pricing)). Local models cost zero at the margin and are priced accordingly — the harness reports the model that actually ran, so requesting `voyage-4-lite` and falling back to `bge-small` does not bill you for Voyage.

Three separate figures, deliberately:

- `cost_per_1k_queries_usd` — what you would actually pay, including provider-side prompt-cache discounts.
- `cost_per_1k_queries_uncached_usd` — every prompt token priced at the cache-miss rate. **This is the comparable number.** DeepSeek caches prompt prefixes and bills hits at roughly 2% of the miss rate, so without this figure whichever strategy ran second looks cheaper than it is. The leaderboard and the cost/quality scatter use it.
- `eval_cost_usd` — the price of judging. Reported separately because it is the cost of measuring, not of serving, and folding it in would make every strategy's cost look identical.

Unknown models fall back to zero rather than crashing the run, and the report names them in a footnote so a zero is never mistaken for free.

## What these metrics do not tell you

LLM-as-judge is not ground truth. Agreement with human grading is good on factoid and numeric questions and weaker on open-ended ones. Mitigations built in: judge with a different model than you generate with, keep the deterministic metrics visible alongside, and render the judge's reasoning for every question so you can audit it. Read the failures before believing the averages.

Absolute values are corpus-specific. The useful output is the ranking of strategies on *your* documents. A faithfulness number from someone else's corpus predicts nothing about yours.
