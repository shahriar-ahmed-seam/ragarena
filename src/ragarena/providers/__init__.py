"""Provider registry: turns a :class:`~ragarena.config.Settings` into clients."""

from __future__ import annotations

from ..cache import ResponseCache
from ..config import Settings
from ..errors import ConfigError
from .base import (
    EmbeddingProvider,
    EmbedResult,
    HTTPProviderBase,
    LLMProvider,
    LLMResponse,
    RerankProvider,
    RerankResult,
    l2_normalise,
)
from .embeddings import FastEmbedEmbeddings, HashEmbeddings, VoyageEmbeddings
from .llm import OpenAICompatLLM
from .rerankers import CrossEncoderReranker, NoopReranker, VoyageReranker

__all__ = [
    "CrossEncoderReranker",
    "EmbedResult",
    "EmbeddingProvider",
    "FastEmbedEmbeddings",
    "HTTPProviderBase",
    "HashEmbeddings",
    "LLMProvider",
    "LLMResponse",
    "NoopReranker",
    "OpenAICompatLLM",
    "RerankProvider",
    "RerankResult",
    "VoyageEmbeddings",
    "VoyageReranker",
    "build_embedder",
    "build_llm",
    "build_reranker",
    "l2_normalise",
]


def build_llm(settings: Settings, cache: ResponseCache | None = None) -> OpenAICompatLLM:
    settings.require_llm()
    return OpenAICompatLLM(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.generator_model,
        timeout_s=settings.llm_timeout_s,
        max_retries=settings.max_retries,
        retry_base_delay_s=settings.retry_base_delay_s,
        cache=cache,
        thinking=settings.llm_thinking,
        rpm=settings.llm_rpm,
    )


def build_embedder(settings: Settings, cache: ResponseCache | None = None):
    provider = settings.embed_provider
    if provider == "voyage":
        settings.require_embeddings()
        return VoyageEmbeddings(
            api_key=settings.voyage_api_key,
            model=settings.embed_model,
            dimension=settings.embed_dimension,
            batch_size=settings.embed_batch_size,
            max_retries=settings.max_retries,
            retry_base_delay_s=settings.retry_base_delay_s,
            cache=cache,
            rpm=settings.voyage_rpm,
        )
    if provider in {"fastembed", "local"}:
        model = settings.embed_model
        if model.startswith("voyage"):
            model = "BAAI/bge-small-en-v1.5"
        return FastEmbedEmbeddings(model=model)
    if provider == "hash":
        return HashEmbeddings(dimension=settings.embed_dimension or 1024)
    raise ConfigError(
        f"Unknown embed provider {provider!r}. Expected one of: voyage, fastembed, hash."
    )


def build_reranker(settings: Settings, cache: ResponseCache | None = None):
    provider = settings.rerank_provider
    if provider in {"none", "", "noop"}:
        return NoopReranker()
    if provider == "voyage":
        settings.require_reranker()
        return VoyageReranker(
            api_key=settings.voyage_api_key,
            model=settings.rerank_model,
            max_retries=settings.max_retries,
            retry_base_delay_s=settings.retry_base_delay_s,
            cache=cache,
            rpm=settings.voyage_rpm,
        )
    if provider in {"crossencoder", "local"}:
        model = settings.rerank_model
        if model.startswith("rerank-"):
            model = "Xenova/ms-marco-MiniLM-L-6-v2"
        return CrossEncoderReranker(model=model)
    raise ConfigError(
        f"Unknown rerank provider {provider!r}. Expected one of: voyage, crossencoder, none."
    )
