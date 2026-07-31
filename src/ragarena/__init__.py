"""RAGArena: head-to-head benchmarking and evaluation for RAG pipelines.

Quick start:

    from ragarena import Settings, load_dataset, build_suite, BenchmarkRunner

    settings = Settings.from_env()
    dataset = load_dataset("meridian")
    runner = BenchmarkRunner(settings, dataset, build_suite())
    result = await runner.run()
    print(result.best().name, result.best().metrics["arena_score"])

Or from the shell:

    ragarena bench --suite default
"""

from __future__ import annotations

from ._version import __version__
from .cache import ResponseCache
from .chunking import (
    FixedWordChunker,
    MarkdownSectionChunker,
    RecursiveChunker,
    SentenceWindowChunker,
    get_chunker,
)
from .config import Settings, get_settings
from .datasets import list_bundled, load_dataset
from .errors import (
    ConfigError,
    DatasetError,
    ProviderError,
    RAGArenaError,
    RateLimitError,
    StrategyError,
)
from .generation import Generator
from .index import MemoryIndex, build_index
from .metrics import Judge
from .presets import DEFAULT_SUITE, PRESETS, build_suite, get_preset
from .report import render_html, write_html, write_json, write_summary
from .runner import BenchmarkRunner, StrategySpec
from .strategies import PipelineConfig, RetrievalContext, Strategy
from .types import (
    Answer,
    Chunk,
    Dataset,
    Document,
    QueryTrace,
    Question,
    RunResult,
    StrategyResult,
)

__all__ = [
    "DEFAULT_SUITE",
    "PRESETS",
    "Answer",
    "BenchmarkRunner",
    "Chunk",
    "ConfigError",
    "Dataset",
    "DatasetError",
    "Document",
    "FixedWordChunker",
    "Generator",
    "Judge",
    "MarkdownSectionChunker",
    "MemoryIndex",
    "PipelineConfig",
    "ProviderError",
    "QueryTrace",
    "Question",
    "RAGArenaError",
    "RateLimitError",
    "RecursiveChunker",
    "ResponseCache",
    "RetrievalContext",
    "RunResult",
    "SentenceWindowChunker",
    "Settings",
    "Strategy",
    "StrategyError",
    "StrategyResult",
    "StrategySpec",
    "__version__",
    "build_index",
    "build_suite",
    "get_chunker",
    "get_preset",
    "get_settings",
    "list_bundled",
    "load_dataset",
    "render_html",
    "write_html",
    "write_json",
    "write_summary",
]
