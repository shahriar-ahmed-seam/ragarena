"""Exception hierarchy for RAGArena."""

from __future__ import annotations


class RAGArenaError(Exception):
    """Base class for every error raised by RAGArena."""


class ConfigError(RAGArenaError):
    """Configuration is missing or invalid."""


class ProviderError(RAGArenaError):
    """A provider (LLM / embeddings / reranker) failed."""

    def __init__(self, provider: str, message: str, status: int | None = None) -> None:
        self.provider = provider
        self.status = status
        prefix = f"[{provider}]"
        if status is not None:
            prefix += f" HTTP {status}"
        super().__init__(f"{prefix} {message}")


class RateLimitError(ProviderError):
    """Provider signalled a rate limit; the caller should back off."""


class DatasetError(RAGArenaError):
    """A dataset could not be loaded or is structurally invalid."""


class IndexError_(RAGArenaError):
    """An index backend failed."""


class StrategyError(RAGArenaError):
    """A strategy is unknown or misconfigured."""
