"""Rank fusion for hybrid retrieval.

Dense cosine similarity and BM25 live on incomparable scales, so fusing them by
raw score is unstable across corpora. Reciprocal Rank Fusion sidesteps this by
using only ordinal position, which is why it is the default here. Score-based
fusion is provided too, since it wins occasionally and the point of RAGArena is
to measure rather than assume.
"""

from __future__ import annotations

from collections.abc import Sequence

RankedList = Sequence[tuple[int, float]]

# The constant from the original RRF paper (Cormack et al., 2009). Dampens the
# influence of the very top ranks so one confident-but-wrong retriever cannot
# dominate the fused list.
RRF_K = 60.0


def reciprocal_rank_fusion(
    ranked_lists: Sequence[RankedList],
    *,
    weights: Sequence[float] | None = None,
    k: float = RRF_K,
) -> list[tuple[int, float]]:
    """Fuse ranked lists by ``sum(weight / (k + rank))``.

    Args:
        ranked_lists: each an ordered sequence of ``(item id, score)``.
        weights: per-list weight, defaults to 1.0 each.
        k: RRF damping constant.

    Returns:
        ``(item id, fused score)`` sorted best first.
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    if len(weights) != len(ranked_lists):
        raise ValueError("weights must match ranked_lists length")

    fused: dict[int, float] = {}
    for ranked, weight in zip(ranked_lists, weights, strict=True):
        for rank, (item_id, _score) in enumerate(ranked, start=1):
            fused[item_id] = fused.get(item_id, 0.0) + weight / (k + rank)
    return sorted(fused.items(), key=lambda pair: (-pair[1], pair[0]))


def _min_max(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [1.0 if hi > 0 else 0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def weighted_score_fusion(
    ranked_lists: Sequence[RankedList],
    *,
    weights: Sequence[float] | None = None,
) -> list[tuple[int, float]]:
    """Min-max normalise each list, then take a weighted sum.

    Keeps score magnitude information that RRF discards, at the cost of being
    sensitive to outliers in either list.
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    if len(weights) != len(ranked_lists):
        raise ValueError("weights must match ranked_lists length")

    fused: dict[int, float] = {}
    for ranked, weight in zip(ranked_lists, weights, strict=True):
        items = list(ranked)
        normalised = _min_max([score for _, score in items])
        for (item_id, _), norm in zip(items, normalised, strict=True):
            fused[item_id] = fused.get(item_id, 0.0) + weight * norm
    return sorted(fused.items(), key=lambda pair: (-pair[1], pair[0]))


def maximal_marginal_relevance(
    candidates: Sequence[tuple[int, float]],
    similarity: object,
    *,
    lambda_mult: float = 0.6,
    top_k: int = 5,
) -> list[tuple[int, float]]:
    """Greedy MMR re-ordering to trade relevance against redundancy.

    Args:
        candidates: ``(item id, relevance)`` best first.
        similarity: callable ``(a, b) -> float`` pairwise item similarity.
        lambda_mult: 1.0 = pure relevance, 0.0 = pure diversity.
        top_k: how many items to select.
    """
    if not candidates:
        return []
    pool = list(candidates)
    selected: list[tuple[int, float]] = [pool.pop(0)]
    sim_fn = similarity  # type: ignore[assignment]

    while pool and len(selected) < top_k:
        best_idx = 0
        best_value = float("-inf")
        for i, (item_id, relevance) in enumerate(pool):
            redundancy = max(
                (float(sim_fn(item_id, chosen_id)) for chosen_id, _ in selected),  # type: ignore[operator]
                default=0.0,
            )
            value = lambda_mult * relevance - (1.0 - lambda_mult) * redundancy
            if value > best_value:
                best_value, best_idx = value, i
        selected.append(pool.pop(best_idx))
    return selected


def dedupe_by_document(
    ranked: Sequence[tuple[int, float]],
    doc_of: object,
    *,
    max_per_doc: int = 2,
) -> list[tuple[int, float]]:
    """Cap how many chunks a single document may contribute.

    Long documents otherwise crowd out the rest of the corpus and answers get
    narrower than the question deserves.
    """
    seen: dict[str, int] = {}
    out: list[tuple[int, float]] = []
    for item_id, score in ranked:
        doc = str(doc_of(item_id))  # type: ignore[operator]
        if seen.get(doc, 0) >= max_per_doc:
            continue
        seen[doc] = seen.get(doc, 0) + 1
        out.append((item_id, score))
    return out
