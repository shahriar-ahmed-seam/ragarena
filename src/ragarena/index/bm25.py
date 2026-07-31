"""BM25 (Okapi) lexical scoring.

Implemented in-package rather than pulled from a dependency so the lexical leg
of hybrid search is transparent, deterministic and cheap to reason about when a
benchmark result looks surprising.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

from ..utils import tokenize


class BM25:
    """Classic BM25 over a static corpus.

    Args:
        corpus: raw documents; tokenised internally.
        k1: term-frequency saturation (1.2-2.0 is the usual band).
        b: length normalisation strength (0 = none, 1 = full).
    """

    def __init__(self, corpus: Sequence[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_tokens: list[list[str]] = [tokenize(doc) for doc in corpus]
        self.doc_len: list[int] = [len(t) for t in self.doc_tokens]
        self.n_docs = len(self.doc_tokens)
        self.avg_len = (sum(self.doc_len) / self.n_docs) if self.n_docs else 0.0

        self.term_freqs: list[Counter[str]] = [Counter(t) for t in self.doc_tokens]
        doc_freq: Counter[str] = Counter()
        for counter in self.term_freqs:
            doc_freq.update(counter.keys())

        # Lucene-style IDF: always positive, so common terms cannot subtract
        # score and flip an otherwise good match negative.
        self.idf: dict[str, float] = {
            term: math.log(1.0 + (self.n_docs - df + 0.5) / (df + 0.5))
            for term, df in doc_freq.items()
        }

    def scores(self, query: str) -> list[float]:
        terms = tokenize(query)
        out = [0.0] * self.n_docs
        if not terms or not self.n_docs:
            return out
        for idx in range(self.n_docs):
            tf = self.term_freqs[idx]
            length = self.doc_len[idx]
            denom_len = self.k1 * (1 - self.b + self.b * (length / self.avg_len or 1.0))
            total = 0.0
            for term in terms:
                freq = tf.get(term)
                if not freq:
                    continue
                total += self.idf.get(term, 0.0) * (freq * (self.k1 + 1)) / (freq + denom_len)
            out[idx] = total
        return out

    def top_k(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        scored = [(i, s) for i, s in enumerate(self.scores(query)) if s > 0.0]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:k]
