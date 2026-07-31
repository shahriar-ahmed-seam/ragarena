"""Chunking strategies.

Chunking is the single cheapest lever on RAG quality and the one most often
left unmeasured, so it is a first-class benchmark axis here: every chunker is
selectable per strategy and recorded in the run config.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Sequence

from .errors import StrategyError
from .types import Chunk, Document

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


def split_sentences(text: str) -> list[str]:
    """Regex sentence splitter: no model download, good enough for chunking."""
    parts = [s.strip() for s in _SENTENCE_END.split(text.strip()) if s.strip()]
    return parts or ([text.strip()] if text.strip() else [])


class Chunker(ABC):
    """Turns a :class:`Document` into retrievable :class:`Chunk` objects."""

    name: str = "base"

    @abstractmethod
    def chunk(self, doc: Document) -> list[Chunk]: ...

    def chunk_all(self, docs: Sequence[Document]) -> list[Chunk]:
        out: list[Chunk] = []
        for doc in docs:
            out.extend(self.chunk(doc))
        return out

    def config(self) -> dict[str, object]:
        return {"chunker": self.name}

    @staticmethod
    def _make(
        doc: Document,
        ordinal: int,
        text: str,
        context_text: str | None = None,
        **metadata: object,
    ) -> Chunk:
        return Chunk(
            id=f"{doc.id}::{ordinal}",
            doc_id=doc.id,
            text=text.strip(),
            ordinal=ordinal,
            title=doc.title,
            context_text=context_text,
            metadata={"source": doc.source, **metadata},
        )


class FixedWordChunker(Chunker):
    """Fixed window of words with overlap. The baseline everyone starts with."""

    name = "fixed"

    def __init__(self, size_words: int = 180, overlap_words: int = 30) -> None:
        if size_words <= 0:
            raise StrategyError("size_words must be positive")
        if overlap_words >= size_words:
            raise StrategyError("overlap_words must be smaller than size_words")
        self.size_words = size_words
        self.overlap_words = overlap_words

    def chunk(self, doc: Document) -> list[Chunk]:
        words = doc.text.split()
        if not words:
            return []
        step = self.size_words - self.overlap_words
        chunks: list[Chunk] = []
        for ordinal, start in enumerate(range(0, len(words), step)):
            window = words[start : start + self.size_words]
            if not window:
                break
            chunks.append(self._make(doc, ordinal, " ".join(window)))
            if start + self.size_words >= len(words):
                break
        return chunks

    def config(self) -> dict[str, object]:
        return {
            "chunker": self.name,
            "size_words": self.size_words,
            "overlap_words": self.overlap_words,
        }


class RecursiveChunker(Chunker):
    """Split on the largest natural boundary that fits, then merge upward.

    Mirrors the widely used recursive character splitter: prefer paragraph
    breaks, fall back to lines, then sentences, then words. Keeps semantic
    units intact far more often than a fixed window.
    """

    name = "recursive"
    SEPARATORS = ["\n\n", "\n", ". ", " "]

    def __init__(self, size_chars: int = 1100, overlap_chars: int = 150) -> None:
        if size_chars <= 0:
            raise StrategyError("size_chars must be positive")
        if overlap_chars >= size_chars:
            raise StrategyError("overlap_chars must be smaller than size_chars")
        self.size_chars = size_chars
        self.overlap_chars = overlap_chars

    def _split(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self.size_chars or not separators:
            return [text]
        sep, *rest = separators
        pieces = text.split(sep)
        out: list[str] = []
        for piece in pieces:
            if len(piece) <= self.size_chars:
                out.append(piece)
            else:
                out.extend(self._split(piece, rest))
        return [p for p in (s.strip() for s in out) if p]

    def _merge(self, pieces: list[str]) -> list[str]:
        merged: list[str] = []
        buffer = ""
        for piece in pieces:
            candidate = f"{buffer}\n\n{piece}" if buffer else piece
            if len(candidate) <= self.size_chars:
                buffer = candidate
                continue
            if buffer:
                merged.append(buffer)
                tail = buffer[-self.overlap_chars :] if self.overlap_chars else ""
                buffer = f"{tail}\n\n{piece}".strip() if tail else piece
            else:
                merged.append(piece)
                buffer = ""
        if buffer:
            merged.append(buffer)
        return merged

    def chunk(self, doc: Document) -> list[Chunk]:
        if not doc.text.strip():
            return []
        pieces = self._split(doc.text.strip(), list(self.SEPARATORS))
        return [
            self._make(doc, i, body)
            for i, body in enumerate(self._merge(pieces))
            if body.strip()
        ]

    def config(self) -> dict[str, object]:
        return {
            "chunker": self.name,
            "size_chars": self.size_chars,
            "overlap_chars": self.overlap_chars,
        }


class SentenceWindowChunker(Chunker):
    """Embed small units, generate from a wider window.

    Retrieval precision improves because each vector covers one idea, while the
    generator still sees surrounding sentences for context. This is why
    :attr:`Chunk.context_text` exists.
    """

    name = "sentence-window"

    def __init__(self, sentences_per_chunk: int = 2, window: int = 3) -> None:
        if sentences_per_chunk <= 0:
            raise StrategyError("sentences_per_chunk must be positive")
        if window < 0:
            raise StrategyError("window must be >= 0")
        self.sentences_per_chunk = sentences_per_chunk
        self.window = window

    def chunk(self, doc: Document) -> list[Chunk]:
        sentences = split_sentences(doc.text)
        if not sentences:
            return []
        chunks: list[Chunk] = []
        starts = range(0, len(sentences), self.sentences_per_chunk)
        for ordinal, start in enumerate(starts):
            core = sentences[start : start + self.sentences_per_chunk]
            if not core:
                break
            lo = max(0, start - self.window)
            hi = min(len(sentences), start + self.sentences_per_chunk + self.window)
            chunks.append(
                self._make(
                    doc,
                    ordinal,
                    " ".join(core),
                    context_text=" ".join(sentences[lo:hi]),
                    window=self.window,
                )
            )
        return chunks

    def config(self) -> dict[str, object]:
        return {
            "chunker": self.name,
            "sentences_per_chunk": self.sentences_per_chunk,
            "window": self.window,
        }


class MarkdownSectionChunker(Chunker):
    """Split on markdown headings, then recursively split oversized sections.

    Section titles are prepended to the chunk body: a heading is free context
    and reliably lifts both lexical and dense retrieval.
    """

    name = "markdown-section"

    def __init__(self, max_chars: int = 1400, overlap_chars: int = 120) -> None:
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars
        self._fallback = RecursiveChunker(size_chars=max_chars, overlap_chars=overlap_chars)

    def chunk(self, doc: Document) -> list[Chunk]:
        text = doc.text.strip()
        if not text:
            return []

        matches = list(_HEADING.finditer(text))
        if not matches:
            return self._fallback.chunk(doc)

        sections: list[tuple[str, str]] = []
        if matches[0].start() > 0:
            preamble = text[: matches[0].start()].strip()
            if preamble:
                sections.append((doc.title or "Overview", preamble))
        for i, match in enumerate(matches):
            heading = match.group(2).strip()
            body_start = match.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[body_start:body_end].strip()
            if body:
                sections.append((heading, body))

        chunks: list[Chunk] = []
        ordinal = 0
        for heading, body in sections:
            prefix = f"{heading}\n"
            if len(body) + len(prefix) <= self.max_chars:
                chunks.append(self._make(doc, ordinal, prefix + body, section=heading))
                ordinal += 1
                continue
            sub = Document(id=doc.id, text=body, title=doc.title, source=doc.source)
            for piece in self._fallback.chunk(sub):
                chunks.append(
                    self._make(doc, ordinal, prefix + piece.text, section=heading)
                )
                ordinal += 1
        return chunks

    def config(self) -> dict[str, object]:
        return {
            "chunker": self.name,
            "max_chars": self.max_chars,
            "overlap_chars": self.overlap_chars,
        }


CHUNKERS: dict[str, type[Chunker]] = {
    FixedWordChunker.name: FixedWordChunker,
    RecursiveChunker.name: RecursiveChunker,
    SentenceWindowChunker.name: SentenceWindowChunker,
    MarkdownSectionChunker.name: MarkdownSectionChunker,
}


def get_chunker(name: str, **kwargs: object) -> Chunker:
    try:
        cls = CHUNKERS[name]
    except KeyError as exc:
        raise StrategyError(
            f"Unknown chunker {name!r}. Available: {', '.join(sorted(CHUNKERS))}"
        ) from exc
    return cls(**kwargs)  # type: ignore[arg-type]
