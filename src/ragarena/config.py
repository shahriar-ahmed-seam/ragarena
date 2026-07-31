"""Environment-driven configuration.

Resolution order for every value: explicit keyword argument > environment
variable > `.env` file (searched upward from the CWD) > built-in default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .errors import ConfigError

_ENV_LOADED = False


def load_env_files(start: Path | None = None, max_up: int = 4) -> None:
    """Load the nearest `.env`, walking up from ``start`` (default: CWD).

    Existing process environment always wins, so CI secrets are never
    clobbered by a stray local file.
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *list(here.parents)[:max_up]]:
        env_file = candidate / ".env"
        if env_file.is_file():
            load_dotenv(env_file, override=False)
            break
    _ENV_LOADED = True


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value.strip()
    return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class Settings:
    """Everything RAGArena needs to talk to the outside world."""

    # --- LLM (OpenAI-compatible chat completions) --------------------------
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    generator_model: str = "deepseek-v4-flash"
    judge_model: str = "deepseek-v4-pro"
    llm_timeout_s: float = 180.0
    # DeepSeek V4 has thinking mode ON by default. Benchmarks need cheap,
    # deterministic, low-variance output, so RAGArena disables it unless asked.
    llm_thinking: bool = False
    generator_temperature: float = 0.0
    judge_temperature: float = 0.0

    # --- Embeddings --------------------------------------------------------
    embed_provider: str = "voyage"  # voyage | fastembed | hash
    embed_model: str = "voyage-4-lite"
    embed_dimension: int | None = None
    voyage_api_key: str = ""
    embed_batch_size: int = 96
    # Client-side pacing for the hosted providers. 0 = no pacing. A Voyage
    # account without a payment method is capped at 3 RPM, which will fail a
    # whole run unless the client throttles itself.
    voyage_rpm: int = 0
    llm_rpm: int = 0

    # --- Reranker ----------------------------------------------------------
    rerank_provider: str = "voyage"  # voyage | crossencoder | none
    rerank_model: str = "rerank-2.5-lite"

    # --- Runner ------------------------------------------------------------
    concurrency: int = 4
    max_retries: int = 4
    retry_base_delay_s: float = 1.5

    # --- Cache -------------------------------------------------------------
    cache_enabled: bool = True
    cache_dir: Path = field(default_factory=lambda: Path(".ragarena_cache"))

    # --- Optional pgvector backend ----------------------------------------
    database_url: str = ""

    # ---------------------------------------------------------------- build
    @classmethod
    def from_env(cls, **overrides: object) -> Settings:
        load_env_files()
        s = cls(
            llm_base_url=_env(
                "RAGARENA_LLM_BASE_URL", "DEEPSEEK_BASE_URL", default="https://api.deepseek.com"
            ).rstrip("/"),
            llm_api_key=_env(
                "RAGARENA_LLM_API_KEY",
                "DEEPSEEK_API_KEY",
                "deepseek_API",
                "OPENAI_API_KEY",
            ),
            generator_model=_env("RAGARENA_GENERATOR_MODEL", default="deepseek-v4-flash"),
            judge_model=_env("RAGARENA_JUDGE_MODEL", default="deepseek-v4-pro"),
            llm_timeout_s=_env_float("RAGARENA_LLM_TIMEOUT_S", 180.0),
            llm_thinking=_env_bool("RAGARENA_LLM_THINKING", False),
            generator_temperature=_env_float("RAGARENA_GENERATOR_TEMPERATURE", 0.0),
            judge_temperature=_env_float("RAGARENA_JUDGE_TEMPERATURE", 0.0),
            embed_provider=_env("RAGARENA_EMBED_PROVIDER", default="voyage").lower(),
            embed_model=_env("RAGARENA_EMBED_MODEL", default="voyage-4-lite"),
            embed_dimension=(
                _env_int("RAGARENA_EMBED_DIMENSION", 0) or None
            ),
            voyage_api_key=_env("VOYAGE_API_KEY", "VOYAGEAI_API_KEY"),
            embed_batch_size=_env_int("RAGARENA_EMBED_BATCH_SIZE", 96),
            voyage_rpm=_env_int("RAGARENA_VOYAGE_RPM", 0),
            llm_rpm=_env_int("RAGARENA_LLM_RPM", 0),
            rerank_provider=_env("RAGARENA_RERANK_PROVIDER", default="voyage").lower(),
            rerank_model=_env("RAGARENA_RERANK_MODEL", default="rerank-2.5-lite"),
            concurrency=max(1, _env_int("RAGARENA_CONCURRENCY", 4)),
            max_retries=max(0, _env_int("RAGARENA_MAX_RETRIES", 4)),
            retry_base_delay_s=_env_float("RAGARENA_RETRY_BASE_DELAY_S", 1.5),
            cache_enabled=_env_bool("RAGARENA_CACHE_ENABLED", True),
            cache_dir=Path(_env("RAGARENA_CACHE_DIR", default=".ragarena_cache")),
            database_url=_env("DATABASE_URL", "RAGARENA_DATABASE_URL"),
        )
        for key, value in overrides.items():
            if value is None:
                continue
            if not hasattr(s, key):
                raise ConfigError(f"Unknown setting: {key!r}")
            setattr(s, key, value)
        return s

    # ---------------------------------------------------------------- guards
    def require_llm(self) -> None:
        if not self.llm_api_key:
            raise ConfigError(
                "No LLM API key found. Set DEEPSEEK_API_KEY (or RAGARENA_LLM_API_KEY) "
                "in your environment or .env file."
            )

    def require_embeddings(self) -> None:
        if self.embed_provider == "voyage" and not self.voyage_api_key:
            raise ConfigError(
                "embed_provider='voyage' needs VOYAGE_API_KEY. Use "
                "RAGARENA_EMBED_PROVIDER=fastembed for local CPU embeddings, or "
                "'hash' for an offline deterministic stub."
            )

    def require_reranker(self) -> None:
        if self.rerank_provider == "voyage" and not self.voyage_api_key:
            raise ConfigError(
                "rerank_provider='voyage' needs VOYAGE_API_KEY. Use "
                "RAGARENA_RERANK_PROVIDER=crossencoder for a local CPU reranker."
            )

    def redacted(self) -> dict[str, object]:
        """Config snapshot safe to write into a results file."""
        return {
            "llm_base_url": self.llm_base_url,
            "generator_model": self.generator_model,
            "judge_model": self.judge_model,
            "llm_thinking": self.llm_thinking,
            "embed_provider": self.embed_provider,
            "embed_model": self.embed_model,
            "rerank_provider": self.rerank_provider,
            "rerank_model": self.rerank_model,
            "concurrency": self.concurrency,
            "voyage_rpm": self.voyage_rpm or "unpaced",
            "llm_rpm": self.llm_rpm or "unpaced",
            "cache_enabled": self.cache_enabled,
            "llm_api_key_set": bool(self.llm_api_key),
            "voyage_api_key_set": bool(self.voyage_api_key),
            "database_url_set": bool(self.database_url),
        }


_SETTINGS: Settings | None = None


def get_settings(refresh: bool = False, **overrides: object) -> Settings:
    global _SETTINGS
    if _SETTINGS is None or refresh or overrides:
        _SETTINGS = Settings.from_env(**overrides)
    return _SETTINGS
