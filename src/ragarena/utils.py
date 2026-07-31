"""Small shared helpers: timing, percentiles, hashing, text normalisation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import unicodedata
from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import Any, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class Timer:
    """Context manager measuring wall-clock milliseconds.

    >>> with Timer() as t:
    ...     pass
    >>> t.ms >= 0
    True
    """

    __slots__ = ("_start", "ms")

    def __init__(self) -> None:
        self._start = 0.0
        self.ms = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.ms = (time.perf_counter() - self._start) * 1000.0


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile (``q`` in 0..100). Empty input -> 0.0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * (q / 100.0)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    frac = pos - low
    return float(ordered[low] * (1 - frac) + ordered[high] * frac)


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    return float(sum(vals) / len(vals)) if vals else 0.0


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def estimate_tokens(text: str) -> int:
    """Cheap tokeniser-free estimate (~4 chars/token), floored at 1.

    Only used when a provider does not report usage. Real usage numbers are
    always preferred so cost figures stay honest.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def normalise_text(text: str) -> str:
    """Lowercase, strip accents/punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _PUNCT.sub(" ", text.lower())
    return _WS.sub(" ", text).strip()


def tokenize(text: str) -> list[str]:
    return normalise_text(text).split()


def slugify(text: str, max_len: int = 64) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len] or "item"


def stable_hash(payload: Any) -> str:
    """Deterministic sha256 of any JSON-serialisable payload."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def batched(items: Sequence[T], size: int) -> list[Sequence[T]]:
    if size <= 0:
        raise ValueError("size must be positive")
    return [items[i : i + size] for i in range(0, len(items), size)]


async def gather_limited(
    items: Sequence[T],
    worker: Callable[[T], Awaitable[R]],
    limit: int = 4,
    on_done: Callable[[int, int], None] | None = None,
) -> list[R]:
    """Run ``worker`` over ``items`` with bounded concurrency, order preserved.

    Exceptions propagate, but only after the in-flight tasks settle, so a
    provider error cannot leave sockets dangling mid-run.
    """
    semaphore = asyncio.Semaphore(max(1, limit))
    results: list[Any] = [None] * len(items)
    completed = 0
    lock = asyncio.Lock()

    async def run(idx: int, item: T) -> None:
        nonlocal completed
        async with semaphore:
            results[idx] = await worker(item)
        if on_done is not None:
            async with lock:
                completed += 1
                on_done(completed, len(items))

    await asyncio.gather(*(run(i, item) for i, item in enumerate(items)))
    return results


def truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " …"


def extract_json_object(raw: str) -> dict[str, Any]:
    """Pull the first JSON object out of an LLM response.

    Handles fenced code blocks and leading prose, which even JSON-mode models
    occasionally emit. Raises ``ValueError`` if nothing parses.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start : i + 1])
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise ValueError(f"No JSON object found in response: {raw[:200]!r}")
