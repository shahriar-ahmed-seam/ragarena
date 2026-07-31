"""Deterministic retrieval metrics.

No LLM involved: these are computed from the ground truth labels, so they are
free, reproducible and the right place to look first when a pipeline regresses.
A retrieved chunk counts as relevant when its document is labelled relevant, or
when it contains one of the question's labelled snippets (chunk-level ground
truth, which survives a chunker change).
"""

from __future__ import annotations

import math

from ..types import Answer, Question, RetrievedChunk
from ..utils import normalise_text, safe_div


def is_relevant(chunk: RetrievedChunk, question: Question) -> bool:
    if chunk.doc_id in question.relevant_doc_ids:
        return True
    if question.relevant_snippets:
        haystack = normalise_text(chunk.text)
        return any(normalise_text(s) in haystack for s in question.relevant_snippets)
    return False


def relevance_vector(chunks: list[RetrievedChunk], question: Question) -> list[int]:
    return [1 if is_relevant(c, question) else 0 for c in chunks]


def hit_rate(chunks: list[RetrievedChunk], question: Question) -> float:
    """1.0 if at least one relevant chunk was retrieved."""
    return 1.0 if any(relevance_vector(chunks, question)) else 0.0


def precision_at_k(chunks: list[RetrievedChunk], question: Question, k: int | None = None) -> float:
    window = chunks[:k] if k else chunks
    rel = relevance_vector(window, question)
    return safe_div(sum(rel), len(rel))


def document_recall(chunks: list[RetrievedChunk], question: Question) -> float:
    """Fraction of labelled relevant documents represented in the results."""
    if not question.relevant_doc_ids:
        return 0.0
    found = {c.doc_id for c in chunks if c.doc_id in question.relevant_doc_ids}
    return len(found) / len(set(question.relevant_doc_ids))


def mrr(chunks: list[RetrievedChunk], question: Question) -> float:
    """Reciprocal rank of the first relevant chunk."""
    for i, rel in enumerate(relevance_vector(chunks, question), start=1):
        if rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(chunks: list[RetrievedChunk], question: Question, k: int | None = None) -> float:
    """Binary-gain nDCG. Rewards putting the relevant chunk first, not just in the list."""
    window = chunks[:k] if k else chunks
    rel = relevance_vector(window, question)
    if not any(rel):
        return 0.0
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(rel))
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(sum(rel), len(rel))))
    return safe_div(dcg, ideal)


def context_precision(chunks: list[RetrievedChunk], question: Question) -> float:
    """Mean precision@i over the positions holding a relevant chunk.

    Rank-sensitive: moving a relevant chunk up raises the score even when the
    retrieved set is unchanged.
    """
    rel = relevance_vector(chunks, question)
    total_relevant = sum(rel)
    if not total_relevant:
        return 0.0
    running = 0
    accumulated = 0.0
    for i, r in enumerate(rel, start=1):
        if r:
            running += 1
            accumulated += running / i
    return accumulated / total_relevant


def citation_validity(answer: Answer | None, chunks: list[RetrievedChunk], question: Question) -> float:
    """Share of the answer's citations that point at a genuinely relevant chunk.

    Catches the failure where retrieval succeeds, the answer is right, and the
    citations point at the wrong passages: fatal for a product that shows
    sources to users, invisible to text-similarity metrics.
    """
    if answer is None or answer.abstained or not answer.citations:
        return 0.0
    rel = relevance_vector(chunks, question)
    good = sum(1 for idx in answer.citations if 1 <= idx <= len(rel) and rel[idx - 1])
    return safe_div(good, len(answer.citations))


def citation_coverage(answer: Answer | None) -> float:
    """1.0 when a non-abstaining answer cited at least one passage."""
    if answer is None or answer.abstained:
        return 0.0
    return 1.0 if answer.citations else 0.0


def abstention_correct(answer: Answer | None, question: Question) -> float:
    """Did the pipeline abstain exactly when it should have?

    Scored on every question: abstaining on an answerable question is as wrong
    as answering an unanswerable one.
    """
    if answer is None:
        return 0.0
    if question.answerable:
        return 0.0 if answer.abstained else 1.0
    return 1.0 if answer.abstained else 0.0


def retrieval_scores(
    chunks: list[RetrievedChunk], question: Question, answer: Answer | None
) -> dict[str, float]:
    """All deterministic metrics for one question."""
    scores = {
        "hit_rate": hit_rate(chunks, question),
        "precision@k": precision_at_k(chunks, question),
        "doc_recall": document_recall(chunks, question),
        "mrr": mrr(chunks, question),
        "ndcg@k": ndcg_at_k(chunks, question),
        "context_precision": context_precision(chunks, question),
        "citation_validity": citation_validity(answer, chunks, question),
        "citation_coverage": citation_coverage(answer),
        "abstention_correct": abstention_correct(answer, question),
    }
    if not question.answerable:
        # Retrieval metrics are undefined without relevant documents; dropping
        # them keeps the unanswerable set from dragging averages toward zero.
        for key in ("hit_rate", "precision@k", "doc_recall", "mrr", "ndcg@k", "context_precision"):
            scores.pop(key)
    return scores
