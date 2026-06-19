"""LLM-as-judge for the free-text pipeline steps (CONST-9, REQ-021).

Some step outputs have no canonical form, so exact match is the wrong tool:
  * Stage-1 decomposition fragments (the wording chosen for an nl_fragment),
  * Stage-2 open-field patterns (a REGEX/MATCH value for a free-text field),
  * Stage-3 structure tie-breaks (when more than one boolean shape is defensible).

For these the judge returns a constrained, typed verdict (`match | partial | miss`
plus a one-line reason) rather than a free-text grade, so scoring stays comparable
across runs. The chat model is lazy-imported via oppp.llm, so importing this module
needs no creds; tests inject a fake `client` to stay hermetic.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Verdict(StrEnum):
    MATCH = "match"
    PARTIAL = "partial"
    MISS = "miss"


class JudgeVerdict(BaseModel):
    """A constrained verdict over one free-text step output."""

    verdict: Verdict
    reason: str = Field(default="", description="One-sentence justification for the verdict.")


class LLMJudge:
    """Score a free-text step output against an expectation with a typed verdict.

    `client` is any object exposing ``.invoke(prompt) -> JudgeVerdict`` (the
    structured-output chat model). It is built lazily from oppp.llm on first use
    when not supplied, so construction never needs creds; pass a fake in tests.
    """

    def __init__(self, *, model: str | None = None, client=None) -> None:
        self._model = model
        self._client = client

    def _get_client(self):
        if self._client is None:
            from oppp.llm import structured

            self._client = structured(JudgeVerdict, model=self._model)
        return self._client

    def judge(self, *, task: str, produced: str, expected: str, context: str = "") -> JudgeVerdict:
        prompt = (
            "You are grading one step of a natural-language-to-machine-query pipeline. "
            "Decide whether the produced output satisfies the expected intent for this "
            "step. Reply with verdict='match' if equivalent, 'partial' if it captures "
            "some but not all of the intent, or 'miss' if it does not, plus a one-line "
            "reason.\n\n"
            f"Step: {task}\n"
            + (f"Context: {context}\n" if context else "")
            + f"Expected: {expected!r}\n"
            f"Produced: {produced!r}\n"
        )
        return self._get_client().invoke(prompt)

    def judge_fragment(self, question: str, fragment: str, expected: str) -> JudgeVerdict:
        return self.judge(
            task="Stage-1 decomposition fragment",
            produced=fragment,
            expected=expected,
            context=f"Question: {question!r}",
        )

    def judge_open_pattern(self, field: str, produced: str, expected: str) -> JudgeVerdict:
        return self.judge(
            task="Stage-2 open-field value/pattern",
            produced=produced,
            expected=expected,
            context=f"Field: {field}",
        )

    def judge_structure(self, question: str, produced: str, expected: str) -> JudgeVerdict:
        return self.judge(
            task="Stage-3 boolean structure tie-break",
            produced=produced,
            expected=expected,
            context=f"Question: {question!r}",
        )
