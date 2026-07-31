# Strategies

A strategy is a named point in one configuration space, not a bespoke class. That keeps the axes composable: any retriever can be paired with any query transform, with or without reranking.

```
query transform  ->  dense / lexical retrieval  ->  fusion  ->  per-doc cap  ->  rerank  ->  top_k
```

## PipelineConfig

```python
from ragarena import PipelineConfig, Strategy

Strategy(
    name="my-pipeline",
    config=PipelineConfig(
        retriever="hybrid",           # dense | lexical | hybrid
        query_transform="multiquery", # none | hyde | multiquery
        rerank=True,
        fusion="rrf",                 # rrf | weighted
        top_k=5,                      # passages handed to the generator
        candidate_k=30,               # pool retrieved before reranking
        dense_weight=1.0,
        lexical_weight=1.0,
        max_per_doc=0,                # 0 disables the per-document cap
        multiquery_n=3,
    ),
    label="My pipeline",
    description="What this is testing",
)
```

Invalid combinations fail at construction, not halfway through a run: `candidate_k < top_k` and pairing HyDE with a lexical-only retriever both raise `StrategyError` immediately.

## The knobs

### `retriever`

- **`lexical`** — BM25 only (Okapi, k1=1.5, b=0.75), implemented in-package so the lexical leg is inspectable. Strong on exact identifiers, numbers and rare terms; blind to paraphrase.
- **`dense`** — cosine similarity over embeddings. Strong on paraphrase; weak when the answer hinges on a token the embedding smooths over, which is most of what an API reference contains.
- **`hybrid`** — both, fused. The default, because the two failure modes are close to complementary.

### `query_transform`

- **`none`** — the question goes straight to the retrievers.
- **`hyde`** — the LLM drafts a hypothetical answer passage and that passage becomes the dense query, on the theory that a document-shaped query embeds closer to real documents than a question does. The original question is kept in the dense query set as well, so a bad hallucinated passage degrades the run rather than destroying it. Costs one extra LLM call per query.
- **`multiquery`** — the LLM writes N paraphrases; every rewrite is retrieved and all result lists are fused. Costs one extra LLM call per query and multiplies retrieval work by N+1.

### `fusion`

- **`rrf`** — Reciprocal Rank Fusion, `Σ weight / (60 + rank)`. Uses ordinal position only, so it does not care that BM25 scores are unbounded and cosine scores sit in [-1, 1]. The default for that reason.
- **`weighted`** — min-max normalise each list, then take a weighted sum. Keeps score magnitude, which occasionally wins, and is sensitive to a single outlier in either list.

### `rerank`

A cross-encoder scores each `(query, candidate)` pair jointly rather than comparing two independently-computed vectors, which is why it is more accurate and why it cannot be precomputed. It reads `candidate_k` candidates and returns `top_k`.

This is the main latency/quality lever. `rerank-2.5-lite` over the network costs a round trip; the local `ms-marco-MiniLM-L-6-v2` costs CPU that scales with `candidate_k` and contends with itself under concurrency.

### `candidate_k` vs `top_k`

`top_k` is what the generator sees. `candidate_k` is the pool the reranker chooses from. Without reranking, `candidate_k` only affects fusion depth. With reranking, a wider pool gives the cross-encoder more to work with — up to the point where recall was never the binding constraint, after which you are paying latency for nothing. The `hybrid-rerank` versus `hybrid-rerank-wide` pair exists to find that point on your corpus.

### `max_per_doc`

Caps how many chunks one document may contribute. A long document otherwise crowds out the rest of the corpus and answers get narrower than the question deserves. Off by default because it can hurt single-document multi-part questions.

## Built-in presets

| Preset | Retriever | Transform | Rerank | top_k / candidates | Isolates |
| --- | --- | --- | --- | --- | --- |
| `bm25-only` | lexical | none | no | 5 / 20 | Lexical baseline |
| `dense-only` | dense | none | no | 5 / 20 | Is the embedding model earning its keep? |
| `hybrid-rrf` | hybrid | none | no | 5 / 20 | Does fusion beat either leg alone? |
| `hybrid-weighted` | hybrid | none | no | 5 / 20 | Rank fusion vs score fusion |
| `hybrid-rerank` | hybrid | none | yes | 5 / 20 | What does a cross-encoder add? |
| `hybrid-rerank-wide` | hybrid | none | yes | 5 / 40 | Does a wider pool help the reranker? |
| `multiquery-rerank` | hybrid | multiquery | yes | 5 / 30 | Query expansion vs a wider pool |
| `hyde-rerank` | hybrid | hyde | yes | 5 / 30 | Hypothetical document vs raw query |

The default suite walks that ladder one change at a time, so each row differs from the one above it in exactly one decision. That is the point: a leaderboard where two rows differ in three ways tells you nothing about which of the three mattered.

```bash
ragarena bench --suite default   # the full ladder
ragarena bench --suite quick     # first four, for a smoke test
ragarena bench --suite all       # every preset including hybrid-weighted
ragarena bench --strategies bm25-only,hybrid-rerank
```

## Chunkers

Chunking is the cheapest lever on RAG quality and the one most often left unmeasured, so it is a first-class axis.

| Chunker | Parameters | Behaviour |
| --- | --- | --- |
| `fixed` | `size_words`, `overlap_words` | Fixed word window with overlap. The baseline. |
| `recursive` | `size_chars`, `overlap_chars` | Splits on the largest natural boundary that fits (paragraph, line, sentence, word), then merges upward with overlap. |
| `markdown-section` | `max_chars`, `overlap_chars` | Splits on headings and prepends the heading to each chunk. Oversized sections fall back to recursive. A heading is free context and lifts both retrieval legs. |
| `sentence-window` | `sentences_per_chunk`, `window` | Embeds a small unit, generates from a wider one. Retrieval precision improves because each vector covers one idea; the generator still sees the surrounding sentences. |

`sentence-window` is why `Chunk` carries both `text` (what gets embedded and scored) and `context_text` (what the generator reads).

```bash
ragarena bench --suite chunking   # one retrieval config, four chunkers
```

Because the chunking sweep holds retrieval constant, any difference is attributable to chunking alone. On the bundled corpus the answer was not the one you would guess from the code — see [findings.md](findings.md).

## Adding a strategy

Nothing to subclass:

```python
import asyncio
from ragarena import BenchmarkRunner, PipelineConfig, Settings, Strategy, load_dataset

candidates = [
    Strategy(
        name=f"rerank-pool-{k}",
        config=PipelineConfig(retriever="hybrid", rerank=True, top_k=5, candidate_k=k),
        label=f"candidate pool {k}",
        description="Sweeping reranker pool depth",
    )
    for k in (10, 20, 40, 80)
]

result = asyncio.run(
    BenchmarkRunner(Settings.from_env(), load_dataset("meridian"), candidates).run()
)
```

To benchmark a different chunker per strategy, pair them with `StrategySpec`:

```python
from ragarena import StrategySpec, get_chunker, get_preset

specs = [
    StrategySpec(strategy=get_preset("hybrid-rerank"), chunker=get_chunker("fixed", size_words=120)),
    StrategySpec(strategy=get_preset("hybrid-rerank"), chunker=get_chunker("fixed", size_words=400)),
]
```

Strategies sharing an identical chunker share an index, so this embeds the corpus once per distinct chunking configuration rather than once per strategy.
