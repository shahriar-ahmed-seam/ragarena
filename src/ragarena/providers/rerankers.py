"""Rerankers: Voyage AI (hosted cross-encoder) and a local fastembed variant."""

from __future__ import annotations

from ..cache import ResponseCache
from ..errors import ConfigError, ProviderError
from ..utils import estimate_tokens
from .base import HTTPProviderBase, RerankResult

VOYAGE_MAX_DOCS = 1000


class VoyageReranker(HTTPProviderBase):
    """Hosted reranking via https://api.voyageai.com/v1/rerank."""

    name = "voyage-rerank"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "rerank-2.5-lite",
        timeout_s: float = 120.0,
        max_retries: int = 4,
        retry_base_delay_s: float = 1.5,
        cache: ResponseCache | None = None,
        rpm: int = 0,
    ) -> None:
        if not api_key:
            raise ConfigError("VoyageReranker requires an API key (VOYAGE_API_KEY).")
        super().__init__(
            base_url="https://api.voyageai.com/v1",
            api_key=api_key,
            timeout_s=timeout_s,
            max_retries=max_retries,
            retry_base_delay_s=retry_base_delay_s,
            cache=cache,
            rpm=rpm,
        )
        self.model = model
        self.name = f"voyage-rerank:{model}"

    async def rerank(
        self, query: str, documents: list[str], *, top_k: int | None = None
    ) -> RerankResult:
        if not documents:
            return RerankResult(ranking=[], model=self.model)
        docs = documents[:VOYAGE_MAX_DOCS]

        payload: dict[str, object] = {
            "query": query,
            "documents": docs,
            "model": self.model,
            "truncation": True,
        }
        if top_k:
            payload["top_k"] = min(top_k, len(docs))

        cache_key = None
        if self.cache is not None:
            cache_key = ResponseCache.make_key("rerank", self.model, payload)
            hit = self.cache.get(cache_key)
            if hit is not None:
                return RerankResult(
                    ranking=[(int(i), float(s)) for i, s in hit["ranking"]],
                    tokens=int(hit.get("tokens", 0)),
                    model=self.model,
                    cached=True,
                )

        body = await self._post("/rerank", payload)
        data = body.get("data")
        if data is None:
            raise ProviderError(self.name, f"missing data in response: {str(body)[:200]}")
        ranking = [
            (int(item["index"]), float(item["relevance_score"]))
            for item in sorted(data, key=lambda d: -float(d["relevance_score"]))
        ]
        tokens = int((body.get("usage") or {}).get("total_tokens") or 0)

        if self.cache is not None and cache_key is not None:
            self.cache.set(
                cache_key, "rerank", self.model, {"ranking": ranking, "tokens": tokens}
            )
        return RerankResult(ranking=ranking, tokens=tokens, model=self.model)


class CrossEncoderReranker:
    """Local CPU cross-encoder via fastembed's ``TextCrossEncoder``.

    Install with ``pip install "ragarena[local]"``. Free, but adds CPU latency
    proportional to the candidate count, which the benchmark will show.
    """

    name = "crossencoder"

    def __init__(
        self,
        *,
        model: str = "Xenova/ms-marco-MiniLM-L-6-v2",
        cache_dir: str | None = None,
        threads: int | None = None,
    ) -> None:
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ConfigError(
                "fastembed is not installed. Run: pip install \"ragarena[local]\""
            ) from exc
        self.model = model
        self._encoder = TextCrossEncoder(model_name=model, cache_dir=cache_dir, threads=threads)
        self.name = f"crossencoder:{model}"

    async def rerank(
        self, query: str, documents: list[str], *, top_k: int | None = None
    ) -> RerankResult:
        if not documents:
            return RerankResult(ranking=[], model=self.model)
        scores = list(self._encoder.rerank(query, documents))
        ranking = sorted(
            ((i, float(s)) for i, s in enumerate(scores)), key=lambda p: -p[1]
        )
        if top_k:
            ranking = ranking[:top_k]
        tokens = estimate_tokens(query) * len(documents) + sum(
            estimate_tokens(d) for d in documents
        )
        return RerankResult(ranking=ranking, tokens=tokens, model=self.model)

    async def aclose(self) -> None:
        return None


class NoopReranker:
    """Identity reranker; keeps strategy code branch-free when reranking is off."""

    name = "none"
    model = "none"

    async def rerank(
        self, query: str, documents: list[str], *, top_k: int | None = None
    ) -> RerankResult:
        ranking = [(i, 1.0 - i * 1e-6) for i in range(len(documents))]
        if top_k:
            ranking = ranking[:top_k]
        return RerankResult(ranking=ranking, model=self.model)

    async def aclose(self) -> None:
        return None
