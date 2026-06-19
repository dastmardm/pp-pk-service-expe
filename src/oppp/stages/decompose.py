"""Stage 1 — decomposition. NL query -> single-field components.

Decomposition's ONLY job is to split the question into single-field fragments
using the user's own words. It must not normalize, correct, expand, or invent
values, and must not consult any controlled vocabulary — grounding to taxonomy
values happens later, in translation.

Backends (pluggable, same interface):
  * llm (default) — LLM structured output; reads the (optionally enhanced) query
    and segments it. Vocab-free by construction. Needs creds / the 'llm' extra.
  * gazetteer — OFFLINE TEST/EVAL DOUBLE ONLY. Detects field mentions by matching
    the taxonomy CSVs + light patterns so the suite and per-stage evaluation can
    run with no network. It deliberately uses vocab, so it is not the production
    decomposer — do not treat it as the design.
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


def get_decomposer(name: str = "llm", **kwargs) -> Decomposer:
    return decomposer_registry.create(name, **kwargs)


def decompose(query: str, service: str = "safety", backend: str = "llm") -> Decomposition:
    """Convenience: run Stage 1 with the named backend."""
    return get_decomposer(backend).decompose(query, get_service(service))


# ---------------------------------------------------------------------------
# Gazetteer (offline) decomposer
# ---------------------------------------------------------------------------
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/]*")
_MAX_NGRAM = 5
_STOP = {"the", "a", "an", "of", "in", "for", "and", "or", "with", "after", "to", "is", "are"}


class GazetteerDecomposer:
    """OFFLINE TEST/EVAL DOUBLE for Stage 1 — not the production decomposer.

    Two detection passes against the taxonomy CSVs: an exact preferred-label pass
    (high precision), then an optional fuzzy pass over the leftover spans so
    misspelled entities ('suntinib' -> Sunitinib) are still detected rather than
    silently dropped. It uses vocab to decompose (which the production `llm`
    decomposer must not), so it exists only to let the test suite and per-stage
    evaluation run without an LLM. Synonym resolution ('homo sapiens') needs the
    TERMite enhancer.
    """

    def __init__(self, fuzzy: bool = True, fuzzy_cutoff: float = 82.0) -> None:
        self.fuzzy = fuzzy
        self.fuzzy_cutoff = fuzzy_cutoff

    def decompose(self, query: str, service: ServiceConfig) -> Decomposition:
        words = [(m.group(0), m.start(), m.end()) for m in _WORD.finditer(query)]
        claimed: set[int] = set()
        lower = query.lower()

        accepted: list[tuple[int, int, str, str, str]] = []  # start,end,field,name,source
        for start_i, end_i, fieldname, hit_name in self._gazetteer_matches(words, service):
            if any(i in claimed for i in range(start_i, end_i + 1)):
                continue
            claimed.update(range(start_i, end_i + 1))
            accepted.append((start_i, end_i, fieldname, hit_name, f"gazetteer:{fieldname}"))

        if self.fuzzy:
            for start_i, end_i, fieldname, hit_name in self._fuzzy_matches(words, claimed, service):
                if any(i in claimed for i in range(start_i, end_i + 1)):
                    continue
                claimed.update(range(start_i, end_i + 1))
                accepted.append((start_i, end_i, fieldname, hit_name, f"gazetteer-fuzzy:{fieldname}"))

        accepted.sort(key=lambda a: a[0])
        comps: list[Component] = [
            Component(
                field=fieldname,
                nl_fragment=hit_name,
                type=ComponentType.FILTER,
                reason=f"The user restricts results to {hit_name!r} on the {fieldname} field.",
                source=source,
            )
            for _, _, fieldname, hit_name, source in accepted
        ]

        _group_multi_value(comps, lower)
        _detect_sex(query, service, comps)
        _detect_preclinical(query, service, comps)
        _detect_year(query, service, comps)
        _detect_questions(lower, service, comps)
        return Decomposition(query=query, service=service.name, components=comps)

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
        out.sort(key=lambda m: (m[1] - m[0]), reverse=True)
        return out

    def _fuzzy_matches(self, words, claimed: set[int], service: ServiceConfig):
        """Fuzzy-detect misspelled entities in unclaimed single tokens.

        Precision guards (tuned empirically against the gold set, see
        docs/06-implementation/build-status.md):
          * single tokens only (multi-word n-grams inflate the ratio via shared
            words, e.g. 'maternal toxicity' ~ 'Oral toxicity');
          * length >= 6 and non-stopword (skip short common words);
          * cutoff 82 with fuzz.ratio (a real typo scores >= 82; near-miss
            English words like 'related'~'repeated' score 80 and are rejected);
          * substring guard — if the candidate is contained in the matched name
            (or vice versa) it's a partial-word hit, not a misspelling
            ('toxicity' in 'Ototoxicity'); a genuine typo is never a clean
            substring of its target.
        """
        out: list[tuple[int, int, str, str, float]] = []
        closed = service.closed_fields()
        indexes = {f: get_index(service.fields[f].taxonomy) for f in closed}
        for i, (word, _s, _e) in enumerate(words):
            if i in claimed:
                continue
            if len(word) < 6 or word.lower() in _STOP or word.isdigit():
                continue
            best_field, best_hit, best_score = None, None, 0.0
            for fieldname in closed:
                hit = indexes[fieldname].best_fuzzy(word, cutoff=self.fuzzy_cutoff)
                if hit is None or hit.score <= best_score:
                    continue
                cand, target = word.lower(), hit.name.lower()
                if cand in target or target in cand:  # substring => partial match, not typo
                    continue
                best_field, best_hit, best_score = fieldname, hit, hit.score
            if best_hit is not None:
                out.append((i, i, best_field, best_hit.name, best_score))
        out.sort(key=lambda m: m[4], reverse=True)
        return [(a, b, f, name) for a, b, f, name, _ in out]


decomposer_registry.add("gazetteer", lambda **kw: GazetteerDecomposer(**kw))


# ---------------------------------------------------------------------------
# Shared detectors (used by gazetteer and termite backends)
# ---------------------------------------------------------------------------
def _group_multi_value(comps: list[Component], lower: str) -> None:
    """Group several values of the same field under one boolean operator.

    'liver disorders or kidney damage' and 'rats or mice' -> an OR group on that
    field; an explicit 'and' with no 'or' -> AND. Applied per field independently
    so each multi-valued field (effects, species, drugs, …) is combined, not just
    effects. Stage 3 turns each group into a nested OR/AND constraint.
    """
    op = BooleanOp.AND if re.search(r"\band\b", lower) and " or " not in lower else BooleanOp.OR
    by_field: dict[str, list[Component]] = {}
    for c in comps:
        if c.type is ComponentType.FILTER:
            by_field.setdefault(c.field, []).append(c)
    for fieldname, members in by_field.items():
        if len(members) > 1:
            for c in members:
                c.boolean_group = BooleanGroup(id=f"{fieldname}-group", op=op)


def _detect_sex(query, service: ServiceConfig, comps):
    if "sex" not in service.fields or any(c.field == "sex" for c in comps):
        return
    m = {
        "female": "Female", "women": "Female", "woman": "Female",
        "male": "Male", "men": "Male", "man": "Male",
    }
    for word, val in m.items():
        if re.search(rf"\b{word}\b", query, re.I):
            comps.append(Component(
                field="sex", nl_fragment=val, type=ComponentType.FILTER,
                reason=f"The user restricts results to {val} subjects.", source="pattern:sex",
            ))
            return


def _detect_preclinical(query, service: ServiceConfig, comps):
    if "isPreclinical" not in service.fields or any(c.field == "isPreclinical" for c in comps):
        return
    if re.search(r"\b(pre[- ]?clinical|non[- ]?clinical)\b", query, re.I):
        comps.append(Component(
            field="isPreclinical", nl_fragment="true", type=ComponentType.FILTER,
            reason="The user restricts results to preclinical (animal) studies.",
            source="pattern:isPreclinical",
        ))


def _detect_year(query, service: ServiceConfig, comps):
    if "documentYear" not in service.fields:
        return
    m = re.search(r"\b(after|before|since|from|until|>|<)\s*(\d{4})\b", query, re.I)
    if not m:
        return
    frag = f"{m.group(1).lower()} {m.group(2)}"
    reason = f"The user restricts the publication year ({frag})."
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


def _detect_questions(lower: str, service: ServiceConfig, comps):
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


# ---------------------------------------------------------------------------
# LLM decomposer (default) — structured output, vocab-free, decompose-only
# ---------------------------------------------------------------------------
class LLMDecomposer:
    """Split the query into single-field components with an LLM. No vocab.

    The model only segments the question — it copies the user's own words into
    each fragment and never normalizes, corrects, expands, or invents values, and
    never consults a controlled vocabulary (that is translation's job). Lazy: the
    chat model is built on first use, so importing this stage needs no creds.
    """

    def __init__(self, model: str | None = None) -> None:
        self._model = model
        self._structured = None  # built lazily via oppp.llm

    def _get(self):
        if self._structured is None:
            from oppp.llm import structured

            self._structured = structured(Decomposition, model=self._model)
        return self._structured

    def decompose(self, query: str, service: ServiceConfig) -> Decomposition:
        prompt = self._build_prompt(query, service)
        result: Decomposition = self._get().invoke(prompt)  # type: ignore[assignment]
        result.query = query
        result.service = service.name
        return result

    def _build_prompt(self, query: str, service: ServiceConfig) -> str:
        fields = ", ".join(service.fields)
        return (
            "You decompose a pharmacology question into single-field components. "
            "This is ONLY segmentation — you split, you do not resolve.\n\n"
            "Hard rules:\n"
            "- Copy the user's own words verbatim into nl_fragment. Do NOT normalize, "
            "correct spelling, translate synonyms, expand abbreviations, or invent values.\n"
            "- Do NOT use any controlled vocabulary or guess canonical labels; grounding "
            "to real values happens in a later stage.\n"
            "- One component per single-field idea. If a field has several values joined "
            "by 'and'/'or' (e.g. 'rats or mice'), emit one component per value and put them "
            "in the same boolean_group with the matching op (OR for 'or', AND for 'and').\n"
            "- type='filter' constrains retrieval; type='question' is what the user wants "
            "reported over the results.\n"
            "- If a square-bracketed '[Recognized entities ...]' hint block is present, you "
            "may use it to choose the right field, but still copy the user's surface words.\n\n"
            f"Available fields: {fields}\n\n"
            f"Question: {query}"
        )


decomposer_registry.add("llm", lambda **kw: LLMDecomposer(**kw))
