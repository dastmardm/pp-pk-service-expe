"""Stage 1 — decomposition. NL query -> single-field components.

Two backends, same interface:
  * gazetteer (default, offline) — detects field mentions by matching the
    taxonomy indexes + light patterns. Runs without an LLM or API keys.
  * llm — LangChain structured output (lazy import; needs deps + creds).
"""

from __future__ import annotations

import re
from typing import Protocol

from oppp.models import (
    BooleanGroup,
    BooleanOp,
    Component,
    ComponentType,
    Decomposition,
)
from oppp.registry import Registry
from oppp.services.base import ServiceConfig, get_service
from oppp.taxonomy.index import get_index


class Decomposer(Protocol):
    def decompose(self, query: str, service: ServiceConfig) -> Decomposition: ...


decomposer_registry: Registry[Decomposer] = Registry("decomposer")


def get_decomposer(name: str = "gazetteer", **kwargs) -> Decomposer:
    return decomposer_registry.create(name, **kwargs)


def decompose(query: str, service: str = "safety", backend: str = "gazetteer") -> Decomposition:
    """Convenience: run Stage 1 with the named backend."""
    return get_decomposer(backend).decompose(query, get_service(service))


# ---------------------------------------------------------------------------
# Gazetteer (offline) decomposer
# ---------------------------------------------------------------------------
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/]*")
_MAX_NGRAM = 5
_STOP = {"the", "a", "an", "of", "in", "for", "and", "or", "with", "after", "to", "is", "are"}


class GazetteerDecomposer:
    def decompose(self, query: str, service: ServiceConfig) -> Decomposition:
        words = [(m.group(0), m.start(), m.end()) for m in _WORD.finditer(query)]
        comps: list[Component] = []
        claimed: set[int] = set()  # word indices already used by a filter match

        # 1. Closed-vocab field detection via the taxonomy gazetteer (longest first).
        matches = self._gazetteer_matches(words, service)
        eff_idx = 0
        lower = query.lower()
        for start_i, end_i, fieldname, hit_name in matches:
            if any(i in claimed for i in range(start_i, end_i + 1)):
                continue
            for i in range(start_i, end_i + 1):
                claimed.add(i)
            bg = None
            if fieldname == "effects":
                eff_idx += 1
            comps.append(
                Component(
                    field=fieldname,
                    nl_fragment=hit_name,
                    type=ComponentType.FILTER,
                    reason=f"The user restricts results to {hit_name!r} on the {fieldname} field.",
                    source=f"gazetteer:{fieldname}",
                    boolean_group=bg,
                )
            )

        # 1b. Boolean grouping for multiple effects (or/and between them).
        eff_comps = [c for c in comps if c.field == "effects"]
        if len(eff_comps) > 1:
            op = BooleanOp.AND if re.search(r"\band\b", lower) and "or" not in lower else BooleanOp.OR
            for c in eff_comps:
                c.boolean_group = BooleanGroup(id="effects-group", op=op)

        # 2. Patterns the gazetteer can't catch.
        self._detect_sex(query, service, comps)
        self._detect_preclinical(query, service, comps)
        self._detect_year(query, service, comps)

        # 3. Question intents (what to report after retrieval).
        self._detect_questions(lower, service, comps)

        return Decomposition(query=query, service=service.name, components=comps)

    # ----- helpers -----------------------------------------------------------
    def _gazetteer_matches(self, words, service: ServiceConfig):
        out: list[tuple[int, int, str, str]] = []
        closed = service.closed_fields()
        indexes = {f: get_index(service.fields[f].taxonomy) for f in closed}
        n = len(words)
        for size in range(min(_MAX_NGRAM, n), 0, -1):
            for i in range(0, n - size + 1):
                phrase = " ".join(w[0] for w in words[i : i + size])
                if size == 1 and phrase.lower() in _STOP:
                    continue
                for fieldname in closed:
                    entry = indexes[fieldname].contains(phrase)
                    if entry is not None:
                        out.append((i, i + size - 1, fieldname, entry.name))
                        break
        # longest matches first so they claim words before shorter ones
        out.sort(key=lambda m: (m[1] - m[0]), reverse=True)
        return out

    def _detect_sex(self, query, service: ServiceConfig, comps):
        if "sex" not in service.fields:
            return
        m = {
            "female": "Female", "women": "Female", "woman": "Female",
            "male": "Male", "men": "Male", "man": "Male",
        }
        for word, val in m.items():
            if re.search(rf"\b{word}\b", query, re.I):
                comps.append(Component(
                    field="sex", nl_fragment=val, type=ComponentType.FILTER,
                    reason=f"The user restricts results to {val} subjects.",
                    source="pattern:sex",
                ))
                return

    def _detect_preclinical(self, query, service: ServiceConfig, comps):
        if "isPreclinical" not in service.fields:
            return
        if re.search(r"\b(pre[- ]?clinical|non[- ]?clinical)\b", query, re.I):
            comps.append(Component(
                field="isPreclinical", nl_fragment="true", type=ComponentType.FILTER,
                reason="The user restricts results to preclinical (animal) studies.",
                source="pattern:isPreclinical",
            ))

    def _detect_year(self, query, service: ServiceConfig, comps):
        if "documentYear" not in service.fields:
            return
        m = re.search(r"\b(after|before|since|from|until|>|<)\s*(\d{4})\b", query, re.I)
        if not m:
            return
        frag = f"{m.group(1).lower()} {m.group(2)}"
        reason = f"The user restricts the publication year ({frag})."
        # A directional year (after/before) outranks a bare gazetteer year match.
        existing = next((c for c in comps if c.field == "documentYear"), None)
        if existing is not None:
            existing.nl_fragment = frag
            existing.reason = reason
            existing.source = "pattern:documentYear"
        else:
            comps.append(Component(
                field="documentYear", nl_fragment=frag, type=ComponentType.FILTER,
                reason=reason, source="pattern:documentYear",
            ))

    def _detect_questions(self, lower: str, service: ServiceConfig, comps):
        have = {c.field for c in comps if c.type == ComponentType.FILTER}

        def add_q(fieldname, frag, reason):
            if fieldname in service.fields and fieldname not in have:
                comps.append(Component(
                    field=fieldname, nl_fragment=frag, type=ComponentType.QUESTION,
                    reason=reason, source="pattern:question",
                ))

        if re.search(r"\b(adrs?|adverse|side effect)", lower) and "effects" not in have:
            add_q("effects", "adverse effects", "The user wants the adverse effects over the retrieved records.")
        if re.search(r"at which dose|which dose|\bdose\b", lower):
            add_q("dose", "at which dose", "The user wants the dose reported per record.")
        if re.search(r"dosing regimen|regimen", lower):
            add_q("doseType", "dosing regimen", "The user wants the dosing regimen per record.")
        if re.search(r"\broute\b", lower):
            add_q("route", "route", "The user wants the route reported per record.")
        if re.search(r"what (are|is) the drugs|which drugs|drugs causing|drugs treating", lower):
            add_q("drugs", "which drugs", "The user wants the list of drugs from the results.")


decomposer_registry.add("gazetteer", lambda **_: GazetteerDecomposer())


# ---------------------------------------------------------------------------
# LLM (LangChain structured output) decomposer — lazy, optional deps
# ---------------------------------------------------------------------------
class LangChainDecomposer:
    """Structured-output decomposition (docs prefer structured output).

    Requires the `llm` extra and credentials in .env. Falls back to nothing here;
    instantiation raises a clear error if deps/keys are missing.
    """

    def __init__(self, model: str | None = None) -> None:
        from oppp.config import get_settings, load_dotenv_if_present

        load_dotenv_if_present()
        s = get_settings()
        if not (s.portkey_api_key and s.portkey_endpoint):
            raise RuntimeError(
                "LLM decomposer needs PORTKEY_* settings in .env (the gazetteer "
                "backend runs offline)."
            )
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("install the 'llm' extra: pip install 'oppp[llm]'") from e

        self._llm = ChatOpenAI(
            api_key=s.portkey_api_key,
            base_url=s.portkey_endpoint,
            model=f"{s.portkey_provider}/{model or s.tool_model}",
            temperature=0,
        )

    def decompose(self, query: str, service: ServiceConfig) -> Decomposition:
        structured = self._llm.with_structured_output(Decomposition)
        prompt = self._build_prompt(query, service)
        result: Decomposition = structured.invoke(prompt)  # type: ignore[assignment]
        result.query = query
        result.service = service.name
        return result

    def _build_prompt(self, query: str, service: ServiceConfig) -> str:
        fields = ", ".join(service.fields)
        return (
            "Decompose the pharmacology question into single-field components.\n"
            f"Available fields: {fields}\n"
            "For each component set: field, nl_fragment, type (filter|question), "
            "a one-sentence reason, and source. 'filter' constrains retrieval; "
            "'question' is answered over the results.\n\n"
            f"Question: {query}"
        )


decomposer_registry.add("llm", lambda **kw: LangChainDecomposer(**kw))
