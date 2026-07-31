"""Answer synthesis with inline citations and explicit abstention.

The generator is deliberately strict: cite every claim by context index, and
when the context does not contain the answer, refuse. Abstention is a measured
outcome here, not a failure mode. Half the value of an eval harness is catching
the pipeline that answers confidently from nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .types import Answer, RetrievedChunk, Usage
from .utils import truncate_words

ABSTAIN_TOKEN = "INSUFFICIENT_CONTEXT"

SYSTEM_PROMPT = f"""You answer questions strictly from the numbered context passages provided.

Rules:
1. Use only facts present in the context. Never add outside knowledge.
2. Cite the passage number in square brackets after every factual claim, e.g. "Requests time out after 30 seconds [2]."
3. Multiple passages may support one claim: "[1][3]".
4. If the context does not contain enough information to answer, reply with exactly
   {ABSTAIN_TOKEN} and nothing else.
5. Be direct and concise: two or three sentences unless the question needs a list.
6. Never mention the words "context", "passage" or "document" in your prose. Just answer.
"""

_CITATION = re.compile(r"\[(\d{1,2})\]")


def build_context_block(chunks: list[RetrievedChunk], max_words_per_chunk: int = 320) -> str:
    """Render retrieved chunks as a numbered, citable context block."""
    parts: list[str] = []
    for chunk in chunks:
        header = f"[{chunk.rank}]"
        if chunk.title:
            header += f" {chunk.title}"
        body = truncate_words(chunk.text.strip(), max_words_per_chunk)
        parts.append(f"{header}\n{body}")
    return "\n\n".join(parts)


def parse_citations(text: str, max_index: int) -> list[int]:
    """Extract unique, in-range 1-based citation indices in order of appearance."""
    seen: list[int] = []
    for match in _CITATION.finditer(text):
        idx = int(match.group(1))
        if 1 <= idx <= max_index and idx not in seen:
            seen.append(idx)
    return seen


def looks_like_abstention(text: str) -> bool:
    stripped = text.strip().strip(".").upper()
    if ABSTAIN_TOKEN in stripped:
        return True
    lowered = text.strip().lower()
    return lowered.startswith(
        (
            "i don't know",
            "i do not know",
            "i cannot answer",
            "i can't answer",
            "not enough information",
            "insufficient information",
        )
    )


@dataclass
class GenerationResult:
    answer: Answer
    usage: Usage = field(default_factory=Usage)
    cached: bool = False


class Generator:
    """Wraps an LLM provider with the citation contract above."""

    def __init__(self, llm, *, model: str | None = None, temperature: float = 0.0) -> None:
        self.llm = llm
        self.model = model
        self.temperature = temperature

    async def generate(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        *,
        max_tokens: int = 700,
    ) -> GenerationResult:
        usage = Usage()

        if not chunks:
            return GenerationResult(
                answer=Answer(text=ABSTAIN_TOKEN, citations=[], abstained=True),
                usage=usage,
            )

        context = build_context_block(chunks)
        response = await self.llm.chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:",
                },
            ],
            model=self.model,
            temperature=self.temperature,
            max_tokens=max_tokens,
        )

        usage.llm_calls += 1
        usage.prompt_tokens += response.prompt_tokens
        usage.completion_tokens += response.completion_tokens
        usage.cached_prompt_tokens += response.cached_prompt_tokens

        text = response.text.strip()
        abstained = looks_like_abstention(text)
        answer = Answer(
            text=text,
            citations=[] if abstained else parse_citations(text, len(chunks)),
            abstained=abstained,
        )
        return GenerationResult(answer=answer, usage=usage, cached=response.cached)
