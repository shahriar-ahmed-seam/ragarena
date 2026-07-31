"""LLM-as-judge metrics: faithfulness, answer relevance, answer correctness.

Two judge calls per answer:

1. **Grounding** - decompose the answer into atomic claims and label each one
   ``supported`` / ``unsupported`` against the retrieved context.
   ``faithfulness = supported / total``. Claim-level beats a holistic 1-5 score:
   a single fabricated sentence in an otherwise correct answer shows up as a
   real number instead of being averaged away.
2. **Answer quality** - relevance to the question and correctness against the
   reference answer, on a 0-4 rubric normalised to 0-1.

The judge runs with thinking disabled and temperature 0 so scores are stable
across re-runs, and every call goes through the response cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..generation import build_context_block
from ..types import Answer, Question, RetrievedChunk, Usage
from ..utils import extract_json_object, safe_div

GROUNDING_SYSTEM = """You are a strict grounding auditor for a retrieval system.

Given CONTEXT passages and an ANSWER, split the answer into atomic factual claims,
then decide for each claim whether the context supports it.

Rules:
- A claim is "supported" only if the context states it or directly entails it.
  Paraphrase is fine; extra specifics that the context does not contain are not.
- Ignore pure meta-sentences that assert no fact (greetings, "here is the answer").
- Numbers, names, dates and thresholds must match exactly to count as supported.

Respond with JSON only:
{"claims": [{"claim": "...", "supported": true, "why": "short reason"}]}"""

QUALITY_SYSTEM = """You grade a generated answer against a question and a reference answer.

Score two dimensions on this 0-4 scale:

relevance - does the answer address what was actually asked?
  0 off-topic | 1 tangential | 2 partially addresses | 3 addresses with minor gaps | 4 fully addresses
correctness - does it agree with the reference answer?
  0 contradicts | 1 mostly wrong | 2 half right or missing key facts | 3 right with a minor omission | 4 fully matches

Judge substance, not style. Ignore formatting, citation markers like [2], and length.
A correct answer phrased differently from the reference still scores 4.

Respond with JSON only:
{"relevance": 0-4, "correctness": 0-4, "why": "one short sentence"}"""


@dataclass
class JudgeOutcome:
    scores: dict[str, float] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)
    usage: Usage = field(default_factory=Usage)


class Judge:
    """LLM-backed grader. Model defaults to the configured judge model."""

    def __init__(self, llm, *, model: str | None = None, temperature: float = 0.0) -> None:
        self.llm = llm
        self.model = model
        self.temperature = temperature

    async def _ask(self, system: str, user: str, usage: Usage, max_tokens: int) -> dict:
        response = await self.llm.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=self.model,
            temperature=self.temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        usage.llm_calls += 1
        usage.prompt_tokens += response.prompt_tokens
        usage.completion_tokens += response.completion_tokens
        usage.cached_prompt_tokens += response.cached_prompt_tokens
        return extract_json_object(response.text)

    # ------------------------------------------------------------- grounding
    async def grounding(
        self, answer: Answer, chunks: list[RetrievedChunk], usage: Usage
    ) -> tuple[float, str]:
        if answer.abstained or not answer.text.strip():
            return 0.0, "abstained"
        context = build_context_block(chunks)
        payload = await self._ask(
            GROUNDING_SYSTEM,
            f"CONTEXT:\n{context}\n\nANSWER:\n{answer.text}",
            usage,
            max_tokens=1200,
        )
        claims = payload.get("claims") or []
        if not isinstance(claims, list) or not claims:
            return 0.0, "judge returned no claims"
        supported = sum(1 for c in claims if isinstance(c, dict) and bool(c.get("supported")))
        note = "; ".join(
            str(c.get("claim", ""))[:90]
            for c in claims
            if isinstance(c, dict) and not c.get("supported")
        )
        return safe_div(supported, len(claims)), (note or "all claims supported")

    # ---------------------------------------------------------------- quality
    async def quality(
        self, question: Question, answer: Answer, usage: Usage
    ) -> tuple[float, float, str]:
        if answer.abstained:
            return 0.0, 0.0, "abstained"
        reference = question.ground_truth or "(no reference answer provided)"
        payload = await self._ask(
            QUALITY_SYSTEM,
            f"QUESTION:\n{question.question}\n\nREFERENCE ANSWER:\n{reference}\n\n"
            f"GENERATED ANSWER:\n{answer.text}",
            usage,
            max_tokens=400,
        )

        def scale(value: object) -> float:
            if not isinstance(value, (int, float, str)):
                return 0.0
            try:
                return max(0.0, min(1.0, float(value) / 4.0))
            except (TypeError, ValueError):
                return 0.0

        return (
            scale(payload.get("relevance")),
            scale(payload.get("correctness")),
            str(payload.get("why", ""))[:300],
        )

    # ------------------------------------------------------------------- all
    async def evaluate(
        self, question: Question, answer: Answer | None, chunks: list[RetrievedChunk]
    ) -> JudgeOutcome:
        outcome = JudgeOutcome()
        if answer is None:
            return outcome

        # Unanswerable questions have no reference answer to grade against.
        # Correct behaviour is abstention, already scored deterministically by
        # `abstention_correct`, so judging here would only add noise.
        if not question.answerable:
            outcome.scores["hallucination_rate"] = 0.0 if answer.abstained else 1.0
            outcome.notes["quality"] = "unanswerable: scored on abstention only"
            return outcome

        faithfulness, note = await self.grounding(answer, chunks, outcome.usage)
        relevance, correctness, why = await self.quality(question, answer, outcome.usage)

        outcome.scores.update(
            {
                "faithfulness": faithfulness,
                "answer_relevance": relevance,
                "answer_correctness": correctness,
            }
        )
        outcome.notes.update({"grounding": note, "quality": why})
        return outcome
