"""USD cost accounting.

Prices are per 1M tokens, taken from the providers' public pricing pages
(DeepSeek: https://api-docs.deepseek.com/quick_start/pricing, Voyage AI:
https://docs.voyageai.com/docs/pricing). Unknown models fall back to 0.0 so a
run never crashes on a price lookup; `Cost.total_usd` is then an underestimate
and the report flags it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import Cost, Usage

USD_PER_MILLION = 1_000_000.0


@dataclass(frozen=True)
class ChatPrice:
    """Per-1M-token prices for a chat model."""

    input_miss: float
    input_hit: float
    output: float


# --- Chat / completion models ---------------------------------------------- #
CHAT_PRICES: dict[str, ChatPrice] = {
    # DeepSeek V4 (2026-04-24 pricing)
    "deepseek-v4-flash": ChatPrice(input_miss=0.14, input_hit=0.0028, output=0.28),
    "deepseek-v4-pro": ChatPrice(input_miss=0.435, input_hit=0.003625, output=0.87),
    # Handy reference points for cross-provider comparisons.
    "gpt-4o-mini": ChatPrice(input_miss=0.15, input_hit=0.075, output=0.60),
    "gpt-4o": ChatPrice(input_miss=2.50, input_hit=1.25, output=10.00),
    "gpt-4.1-mini": ChatPrice(input_miss=0.40, input_hit=0.10, output=1.60),
    # Anything served locally is free at the margin.
    "ollama": ChatPrice(input_miss=0.0, input_hit=0.0, output=0.0),
}

# --- Embedding models (per 1M tokens) -------------------------------------- #
EMBED_PRICES: dict[str, float] = {
    "voyage-4-large": 0.12,
    "voyage-4": 0.06,
    "voyage-4-lite": 0.02,
    "voyage-context-4": 0.12,
    "voyage-code-3": 0.18,
    "voyage-3-large": 0.18,
    "voyage-3.5": 0.06,
    "voyage-3.5-lite": 0.02,
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
}

# --- Rerankers (per 1M tokens) --------------------------------------------- #
RERANK_PRICES: dict[str, float] = {
    "rerank-2.5": 0.05,
    "rerank-2.5-lite": 0.02,
    "rerank-2": 0.05,
    "rerank-2-lite": 0.02,
}

# Local / self-hosted models: no marginal cost.
FREE_MODEL_MARKERS = ("bge-", "minilm", "ms-marco", "local", "hash", "e5-", "gte-", "jina-")


def _is_free(model: str) -> bool:
    m = model.lower()
    return any(marker in m for marker in FREE_MODEL_MARKERS)


def chat_price(model: str) -> ChatPrice | None:
    if model in CHAT_PRICES:
        return CHAT_PRICES[model]
    if _is_free(model):
        return ChatPrice(0.0, 0.0, 0.0)
    # Tolerate suffixed deployment names like "deepseek-v4-flash-preview".
    for known, price in CHAT_PRICES.items():
        if model.startswith(known):
            return price
    return None


def embed_price(model: str) -> float | None:
    if model in EMBED_PRICES:
        return EMBED_PRICES[model]
    if _is_free(model):
        return 0.0
    return None


def rerank_price(model: str) -> float | None:
    if model in RERANK_PRICES:
        return RERANK_PRICES[model]
    if _is_free(model) or model in {"", "none"}:
        return 0.0
    return None


def llm_cost(model: str, prompt_tokens: int, cached_tokens: int, completion_tokens: int) -> float:
    price = chat_price(model)
    if price is None:
        return 0.0
    fresh = max(0, prompt_tokens - cached_tokens)
    total = (
        fresh * price.input_miss
        + cached_tokens * price.input_hit
        + completion_tokens * price.output
    )
    return total / USD_PER_MILLION


def compute_cost(
    usage: Usage,
    *,
    llm_model: str,
    embed_model: str,
    rerank_model: str,
    ignore_prompt_cache: bool = False,
) -> Cost:
    """Turn a token tally into a USD breakdown.

    ``ignore_prompt_cache=True`` prices every prompt token at the cache-miss
    rate. Providers like DeepSeek cache prompt prefixes server-side and bill
    hits at roughly 2% of the miss rate, which is great in production but makes
    two benchmark runs over the same corpus incomparable: whichever ran second
    looks cheaper. The uncached figure is the one to compare strategies on.
    """
    ep = embed_price(embed_model) or 0.0
    rp = rerank_price(rerank_model) or 0.0
    return Cost(
        llm_usd=llm_cost(
            llm_model,
            usage.prompt_tokens,
            0 if ignore_prompt_cache else usage.cached_prompt_tokens,
            usage.completion_tokens,
        ),
        embed_usd=usage.embed_tokens * ep / USD_PER_MILLION,
        rerank_usd=usage.rerank_tokens * rp / USD_PER_MILLION,
    )


def unpriced_models(*models: str) -> list[str]:
    """Models we had no price for, so the report can add a caveat."""
    missing: list[str] = []
    for m in models:
        if not m or m == "none":
            continue
        if (
            chat_price(m) is None
            and embed_price(m) is None
            and rerank_price(m) is None
        ):
            missing.append(m)
    return missing
