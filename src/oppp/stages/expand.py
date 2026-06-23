"""Stage -1 — query expansion (runs before Stage 0 enhancement).

An expander reads the raw NL query and returns an :class:`ExpandedQuery`: a
clearer, fully-spelled-out rewrite of the same question. Its only job is to make
the query easier for the downstream NER (TERMite) and the vocab-free decomposer
to read — it expands abbreviations and clarifies phrasing but MUST NOT add, drop,
or change any entity, value, or filter.

  'What are the ADRs of ADC after single intravenous administration in male?'
    -> 'What adverse drug reactions (ADRs) have been reported following a single
        intravenous administration of the antibody-drug conjugate (ADC) in male
        subjects?'

Why it helps: an expanded surface form lets the recognizer match terms it would
otherwise miss (e.g. 'ADC' -> 'antibody-drug conjugate (ADC)', which the drug
hierarchy can recognize) without the decomposer having to know any vocabulary.

Backends (pluggable by name):
  * llm  — default. Rewrites via the central LLM factory (temperature 0 + seed).
           Degrades to pass-through when no LLM is configured (offline / no creds),
           so importing or running without the 'llm' extra never fails.
  * noop — returns the query unchanged (used by hermetic/offline doubles).

The original query is always preserved on the result for the audit record.
"""

from __future__ import annotations

from typing import Protocol

from oppp.models import ExpandedQuery, QueryExpansion
from oppp.registry import Registry
from oppp.services.base import ServiceConfig, get_service


class Expander(Protocol):
    def expand(self, query: str, service: ServiceConfig) -> ExpandedQuery: ...


expander_registry: Registry[Expander] = Registry("expander")


def get_expander(name: str = "llm", **kwargs) -> Expander:
    return expander_registry.create(name, **kwargs)


def expand(query: str, service: str = "safety", backend: str = "llm") -> ExpandedQuery:
    """Convenience: run Stage -1 with the named backend."""
    return get_expander(backend).expand(query, get_service(service))


# ---------------------------------------------------------------------------
# No-op (offline double)
# ---------------------------------------------------------------------------
class NoopExpander:
    """Pass the query through untouched."""

    def expand(self, query: str, service: ServiceConfig) -> ExpandedQuery:
        return ExpandedQuery(text=query, original=query, source="noop")


expander_registry.add("noop", lambda **kw: NoopExpander(**kw))


# ---------------------------------------------------------------------------
# LLM expander (default)
# ---------------------------------------------------------------------------
_PROMPT = (
    "You rewrite a pharmacology question into a clearer, fully spelled-out form so a "
    "downstream entity recognizer and parser can read it more reliably.\n\n"
    "Rules:\n"
    "- Expand abbreviations and acronyms to their full term, keeping the acronym in "
    "parentheses: 'ADR' -> 'adverse drug reaction (ADR)', 'ADC' -> 'antibody-drug "
    "conjugate (ADC)', 'MTD' -> 'maximum tolerated dose (MTD)', 'NOAEL' -> 'no observed "
    "adverse effect level (NOAEL)', 'IV' -> 'intravenous'.\n"
    "- Clarify phrasing into one well-formed sentence.\n"
    "- Do NOT add, drop, or change any entity, value, drug, species, dose, route, sex, "
    "age, or filter. Keep every concept the user mentioned and add none. This is a "
    "faithful rewrite, never a reinterpretation — same meaning, clearer words.\n"
    "- PRESERVE the exact spelling and capitalization of every disease, effect, "
    "finding, drug, assay, parameter, or other domain term EXACTLY as the user wrote it "
    "('Mutagenicity' stays 'Mutagenicity', not 'mutagenicity'; 'Ames Test' stays 'Ames "
    "Test'). These are matched case-sensitively downstream. Only reword the connecting "
    "glue, never the terms themselves.\n"
    "- Do NOT append clarifying nouns to a term ('Ames Test' must NOT become 'Ames Test "
    "result'; 'NOAEL' must NOT become 'NOAEL value'). Expanding an acronym is allowed; "
    "adding a new word that the user did not write is not.\n"
    "- If the question is already clear, return it essentially unchanged.\n\n"
    "Question: {query}\n\n"
    "Return the rewritten question in `expanded`."
)


class LLMExpander:
    """Rewrite the query with an LLM (clarify + expand abbreviations).

    Lazy: the structured model is built on first use via :mod:`oppp.llm`, so import
    needs no creds. When the LLM is unavailable (no PORTKEY_* / no 'llm' extra) or a
    call fails, it falls back to passing the query through unchanged — the stage is
    always *present* but never *fatal*.
    """

    def __init__(self, model: str | None = None) -> None:
        self._model = model
        self._structured = None  # built lazily

    def _get(self):
        if self._structured is None:
            from oppp.llm import structured

            self._structured = structured(QueryExpansion, model=self._model)
        return self._structured

    def expand(self, query: str, service: ServiceConfig) -> ExpandedQuery:
        try:
            from oppp.llm import LLMUnavailable

            try:
                result: QueryExpansion = self._get().invoke(_PROMPT.format(query=query))
            except LLMUnavailable:
                return ExpandedQuery(text=query, original=query, source="noop(no-llm)")
        except Exception:  # pragma: no cover - any build/call failure -> pass through
            return ExpandedQuery(text=query, original=query, source="noop(error)")
        text = (result.expanded or "").strip() or query
        return ExpandedQuery(text=text, original=query, source="llm")


expander_registry.add("llm", lambda **kw: LLMExpander(**kw))
