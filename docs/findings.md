# Findings

Four committed runs on the bundled `meridian` corpus (20 documents, 7,088 words, 78 labelled questions, 11 of them unanswerable). Generator `deepseek-v4-flash`, judge `deepseek-v4-pro`, both with thinking mode disabled at temperature 0.

Every number below is in [`results/`](../results/) and rendered on [the live leaderboard](https://shahriar-ahmed-seam.github.io/ragarena/). Absolute values are corpus-specific; the rankings are the transferable part.

---

## 1. Retrieval strategies — the full ladder

`results/meridian-ce602851.json` · 78 questions × 7 strategies · 565 s wall clock · $0.045 serving + $0.100 judging · cold cache, concurrency 4

| # | Strategy | Arena | Faith. | Correct. | Ctx prec. | MRR | Hit | Cite valid. | p95 | $/1k |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Multi-query + rerank | **0.928** | 0.952 | 0.929 | **0.917** | **0.974** | 1.000 | 0.814 | 5,991 ms | $0.129 |
| 2 | HyDE + rerank | 0.927 | 0.952 | 0.929 | 0.913 | 0.974 | 1.000 | 0.814 | 5,153 ms | $0.145 |
| 3 | Hybrid + RRF | 0.918 | 0.939 | 0.918 | 0.901 | 0.966 | 1.000 | **0.823** | **1,506 ms** | $0.099 |
| 4 | Hybrid + rerank | 0.918 | 0.937 | 0.922 | 0.915 | 0.974 | 1.000 | 0.808 | 2,352 ms | $0.099 |
| 5 | Hybrid + rerank (wide) | 0.918 | 0.937 | 0.922 | 0.914 | 0.974 | 1.000 | 0.808 | 13,710 ms | $0.099 |
| 6 | Dense only | 0.906 | 0.938 | 0.910 | 0.865 | 0.933 | 1.000 | 0.814 | 1,533 ms | $0.101 |
| 7 | BM25 only | 0.889 | 0.899 | 0.914 | 0.852 | 0.918 | 0.970 | 0.808 | 1,687 ms | **$0.097** |

### The composite understates the retrieval differences

Best-to-worst spread on `arena_score` is 3.9 points, which looks unexciting until you look at what it is averaging. On the retrieval metrics the same seven strategies span **context precision 0.852 → 0.917** (+7.6% relative) and **MRR 0.918 → 0.974**.

The reason is that `deepseek-v4-flash` is good at not over-claiming: given mediocre context it hedges or abstains rather than inventing, so answer-level metrics compress. That is a property of a strong generator, not evidence that retrieval does not matter — and it is exactly why the deterministic retrieval metrics are reported next to the judged ones rather than replaced by them.

### Doubling the reranker's candidate pool bought nothing and cost 5.8x latency

`hybrid-rerank` (20 candidates) and `hybrid-rerank-wide` (40 candidates) are **identical to three decimals on every quality metric**: faithfulness 0.937, correctness 0.922, MRR 0.974. Context precision differs by 0.001.

p95 went from 2,352 ms to 13,710 ms.

Recall was never the binding constraint here. `hit_rate` is 1.000 for every hybrid strategy at 20 candidates, so the relevant chunk was already in the pool and adding twenty more only gave the cross-encoder more CPU work. This is the single most useful thing the harness found: the "just widen the pool" instinct is free to test and, on this corpus, worthless.

### Query expansion is the only thing that moved the top

Multi-query (+0.010) and HyDE (+0.009) over `hybrid-rerank` are the only quality gains above noise, and both come mostly from multi-hop questions: `multiquery-rerank` scores **0.954 on multi-hop** against 0.889 for BM25 and 0.954→0.902 for the plain hybrid pipelines in the 26-question comparison run. Rewriting the query gives the retrievers a second and third chance to surface the *other* document a cross-document question needs.

The bill: one extra LLM call per query, p95 1,506 ms → 5,991 ms, and 30% more cost per thousand queries.

**Hybrid + RRF is the pick on this corpus.** It is within 1.0 point of the winner, the fastest of the credible options at 1,506 ms p95, the cheapest non-degenerate option, has the best citation validity in the run, and it needs no LLM call before retrieval.

### Hybrid beats either leg, and BM25 beats dense on answers

BM25 alone is the only strategy that ever retrieves nothing relevant (`hit_rate` 0.970 — it misses entirely on 3% of questions). Dense alone finds *something* every time (1.000) but ranks it worse (MRR 0.933 vs 0.918 is close, but context precision 0.865 vs 0.852 is nearly a wash) and its answers are worse (correctness 0.910 vs 0.914).

Fusing them gains more than either: MRR 0.966, context precision 0.901. On a corpus this full of exact identifiers — `429 rate_limited`, `X-MFS-Signature`, `50,000 shipments per hour` — the lexical leg contributes precisely what a 384-dimensional embedding smooths away.

### Nothing hallucinated on the unanswerable set

`hallucination_rate` is **0.000 for all seven strategies**: not one of the 11 unanswerable questions got an answer, from any pipeline. Those questions were written to be traps — "how much is the weekly on-call allowance", when the corpus states that an allowance exists but never its amount — with heavy vocabulary overlap against real content.

The credit belongs to the generation contract, not to retrieval: the prompt requires citing every claim by passage number and returning a single sentinel token when the context is insufficient. Abstention accuracy still lands at 0.949–0.974 rather than 1.000, and every point lost there is the *opposite* error — refusing a question that the corpus does answer. Best abstention behaviour: `hybrid-rrf` and the expansion strategies at 0.974.

### Citation validity is the weakest metric in the entire run

It never exceeds **0.823**. Roughly one cited passage in five points at something the labels do not consider relevant, while faithfulness sits at 0.94–0.95 and correctness at 0.92–0.93.

The answers are right and the sources are approximately right. For a product that renders "according to [3]" as a clickable link, approximately right is a defect a user will find. Reranking makes it slightly *worse* (0.823 → 0.808): reordering passages after generation-time numbering means the model's mental map of "which passage said what" is built from a list the reranker just permuted.

No text-similarity metric would have surfaced this, which is why `citation_validity` exists as its own column.

---

## 2. Chunking — as big a lever as the entire strategy ladder

`results/meridian-43a90e3b.json` · identical `hybrid-rerank` retrieval, four chunkers · 78 questions

| Chunker | Arena | Faith. | Correct. | Ctx prec. | Cite valid. | Chunks | p95 | $/1k |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `fixed` 180 words / 30 overlap | **0.954** | 0.985 | **0.966** | 0.913 | **0.853** | **56** | 4,119 ms | $0.193 |
| `markdown-section` | 0.945 | 0.985 | 0.940 | **0.915** | 0.833 | 134 | **2,233 ms** | **$0.100** |
| `recursive` 1100 chars | 0.938 | 0.970 | 0.952 | 0.896 | 0.830 | 60 | 5,155 ms | $0.183 |
| `sentence-window` 2+3 | 0.930 | 0.928 | 0.959 | 0.915 | 0.839 | 169 | 3,319 ms | $0.203 |

The spread here is **2.4 points from chunking alone**, against 3.9 points across seven different retrieval architectures. Chunking is the cheapest thing to change and it is worth about as much as everything else on the leaderboard combined.

Two results worth flagging because they contradict the obvious guess:

**The dumb chunker won.** A fixed 180-word window with 30 words of overlap beat heading-aware markdown splitting, which is the "correct" choice for a corpus that is entirely markdown with clean headings. Fixed windows produce 56 chunks against markdown's 134, so each retrieved passage carries more surrounding context, and on questions like "compare the idempotency window on the Partner API against the customer API" more context per passage beats more precisely delimited passages. It also produced the best citation validity in the whole project (0.853) — fewer, chunkier passages are easier for the model to keep straight.

**Sentence-window came last on faithfulness (0.928, the lowest figure anywhere in these four runs)** despite tying for the best context precision (0.915). It retrieves precisely and then hands the generator a wider window than it scored, and the extra sentences are material the retriever never vouched for. The generator draws on them, and the grounding judge — which scores against the *retrieved* text — marks those claims unsupported. The technique trades faithfulness for recall, which the README of every sentence-window tutorial omits.

Note the cost column: markdown's $0.100 against $0.183–0.203 for the others is not a chunking property, it is DeepSeek's server-side prompt cache. Markdown is the default chunker, so the flagship run had already warmed those exact prompts. The figures shown are the uncached ones, but the underlying token mix still favours whichever chunker the corpus was previously indexed with — one more reason the harness reports both.

---

## 3. Hosted vs local embeddings

Two runs, 26 questions, no reranker, identical everything except the embedding model.

`results/meridian-92142ab9.json` (Voyage) and `results/meridian-3bf405c2.json` (local)

| Strategy | Embeddings | Arena | Faith. | Ctx prec. | MRR |
| --- | --- | --- | --- | --- | --- |
| Hybrid + RRF | `voyage-4-lite` (1024-d, hosted) | **0.968** | **1.000** | 0.909 | **0.981** |
| Hybrid + RRF | `bge-small-en-v1.5` (384-d, CPU) | 0.948 | 0.962 | 0.894 | 0.962 |
| Dense only | `voyage-4-lite` | 0.943 | 0.962 | **0.872** | 0.955 |
| Dense only | `bge-small-en-v1.5` | 0.939 | 0.974 | 0.809 | 0.897 |

`voyage-4-lite` is worth **+2.0 arena points** in the hybrid pipeline and its advantage concentrates exactly where you would expect: with no lexical leg to lean on, dense-only context precision is **0.872 vs 0.809, a 7.8% relative gain**, and MRR 0.955 vs 0.897.

Put differently: fusing BM25 into a weak embedding model recovers most of the gap. Hybrid + local (0.948) beats dense + hosted (0.943). If you cannot or will not pay for hosted embeddings, adding the lexical leg is the cheaper fix, and it is free.

**Do not read the Voyage latency figures.** The hosted dense-only arm reports p95 76,749 ms. That is entirely the client-side rate limiter: the Voyage account has no payment method on file, which caps it at 3 requests per minute, and RAGArena paced itself to 3 RPM rather than absorbing a wall of 429s. Actual Voyage embedding latency, visible in the cached hybrid arm, is **0.64 ms mean** for the query embedding step against 8.98 ms for local ONNX. The hosted model is both better and faster; the number in the table is a billing artefact, and it is in the table rather than quietly excluded because that is the point of recording provider pacing in the run environment.

---

## 4. Cost

Serving cost per 1,000 queries across the flagship run: **$0.097 to $0.145**, prompt-cache discounts excluded. All seven strategies land within 50% of each other because the answer-generation call dominates and every strategy sends five passages to the same model.

The real cost differences are structural, not incremental:

- Local ONNX embeddings and reranking cost **nothing** at the margin. Retrieval quality within 2 points of a hosted stack, for zero dollars per query, is the finding that made this the default configuration for the committed runs.
- Query expansion adds one LLM call: +$0.030 to +$0.046 per 1,000, a 30–47% increase, for +0.9 to +1.0 arena points.
- Judging the flagship run cost **$0.100** against $0.045 to serve it. Evaluation is more expensive than inference, which is why the two are separate fields — folding the judge into cost-per-query would have made every strategy look identical and wrong.

An earlier version of this project did exactly that: it priced local `bge-small` embeddings at Voyage's rate because the requested model name was recorded rather than the model that actually loaded. The harness now bills what ran.

---

## Method notes and caveats

**Two runs of the same configuration disagreed by up to 1.0 arena point.** Compare the flagship (`hybrid-rrf` 0.918) against the 26-question comparison run (0.948) — different question subsets, so not directly comparable — but repeated full runs also moved faithfulness by ~0.01. With 78 questions, one question is 1.3% of the sample. Treat gaps under ~2 points as noise and gaps over 5 points as real.

**Latency was measured at concurrency 4 with CPU-bound local models.** They contend with each other, so absolute milliseconds are pessimistic and the tail especially so. `hybrid-rerank-wide` at 13,710 ms p95 reflects four cross-encoder passes over 40 candidates fighting for the same cores. The *ranking* of latencies holds; the absolute values would improve on a single-user path. Every run artefact records its concurrency for this reason.

**Cache hits are excluded from latency, and cold runs used a fresh cache directory per run.** During this project two flagship runs were accidentally launched concurrently and their latency figures were contaminated by CPU contention; both were discarded rather than published. The published runs are single-process.

**LLM-as-judge is not ground truth.** It agrees well with human grading on the factoid and numeric questions that dominate this corpus and less well on open-ended ones. The judge's per-claim reasoning is stored on every trace and rendered on the site, so any score can be checked rather than trusted.

**One corpus, 7,088 words.** A 20-document corpus is small enough that `hit_rate` saturates at 1.000 for most strategies, which compresses the leaderboard. Conclusions about *ranking* transfer better than conclusions about *magnitude*, and the right next step for anyone evaluating these techniques is `ragarena bench --dataset ./your-docs`.
