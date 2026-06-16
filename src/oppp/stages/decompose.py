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
    """Offline Stage-1 backend.

    Two detection passes against the taxonomy CSVs: an exact preferred-label pass
    (high precision), then an optional fuzzy pass over the leftover spans so
    misspelled entities ('suntinib' -> Sunitinib) are still detected rather than
    silently dropped. Synonyms not present in the CSVs (e.g. 'homo sapiens') still
    need the TERMite backend.
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

        _group_effects(comps, lower)
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
def _group_effects(comps: list[Component], lower: str) -> None:
    eff = [c for c in comps if c.field == "effects"]
    if len(eff) > 1:
        op = BooleanOp.AND if re.search(r"\band\b", lower) and " or " not in lower else BooleanOp.OR
        for c in eff:
            c.boolean_group = BooleanGroup(id="effects-group", op=op)


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


# ---------------------------------------------------------------------------
# TERMite (SciBite NER) decomposer — the design's intended Stage-1 seeder
# ---------------------------------------------------------------------------
# PP TERMite vocabulary id -> the entity type used in ServiceConfig.termite_type_map.
TERMITE_VOCAB_TO_TYPE = {
    "PP_DRUG": "DRUG",
    "PP_AE": "ADVERSE_EVENT",
    "PP_TOX": "TOXICITY_PARAMETER",
    "PP_SPECIES": "SPECIES",
    "PP_ROUTE": "ROUTE",
    "PP_INDICATION": "INDICATION",
    "PP_TARGET": "TARGET",
    "PP_PK": "PARAMETER",
    "PP_AGE": "AGE",
}


class TermiteDecomposer:
    """Annotate entities with SciBite TERMite, then map them to fields.

    TERMite resolves synonyms, brand names, and variants to preferred labels
    (e.g. 'homo sapiens' -> Human, 'Columvi' -> Glofitamab) which the offline
    gazetteer cannot. Unclaimed spans + patterns/questions fall back to the
    gazetteer so recall is preserved.

    Needs the SciBite toolkit and TERMITE_* credentials in .env (lazy, like the
    'llm' backend).
    """

    def __init__(self, fallback: bool = True, fuzzy_fallback: bool = True) -> None:
        from oppp.config import get_settings, load_dotenv_if_present

        load_dotenv_if_present()
        s = get_settings()
        if not (s.termite_home and s.termite_client_name and s.termite_client_secret):
            raise RuntimeError(
                "termite decomposer needs TERMITE_HOME/AUTH_URL/CLIENT_NAME/"
                "CLIENT_SECRET in .env (the gazetteer backend runs offline)."
            )
        try:
            from scibite_toolkit import termite7
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "install the SciBite toolkit to use the termite backend"
            ) from e

        self._builder_factory = termite7.Termite7RequestBuilder
        self._cfg = s
        self._fallback = GazetteerDecomposer(fuzzy=fuzzy_fallback) if fallback else None

    def _annotate(self, query: str, vocabs: list[str]):
        b = self._builder_factory()
        b.set_token_url(self._cfg.termite_auth_url)
        b.set_url(self._cfg.termite_home)
        b.set_oauth2(self._cfg.termite_client_name, self._cfg.termite_client_secret)
        return b.annotate_text(text=query, vocabulary=vocabs)

    def decompose(self, query: str, service: ServiceConfig) -> Decomposition:
        vocabs = list(TERMITE_VOCAB_TO_TYPE)
        annotation = self._annotate(query, vocabs)

        comps: list[Component] = []
        for group in (annotation or {}).get("included", []) or []:
            for ent in group.get("entities", []) or []:
                vocab = ent.get("vocabularyId")
                etype = TERMITE_VOCAB_TO_TYPE.get(vocab)
                field_name = service.termite_type_map.get(etype) if etype else None
                if not field_name or field_name not in service.fields:
                    continue
                name = ent.get("name", "").strip()
                if not name:
                    continue
                comps.append(Component(
                    field=field_name, nl_fragment=name, type=ComponentType.FILTER,
                    reason=f"TERMite annotated {name!r} as {etype} -> {field_name}.",
                    source=f"termite:{vocab}",
                ))

        # Fill gaps (unmatched closed/open fields, patterns, questions) with the gazetteer.
        if self._fallback is not None:
            existing = {(c.field, c.nl_fragment.lower()) for c in comps}
            for g in self._fallback.decompose(query, service).components:
                if (g.field, g.nl_fragment.lower()) not in existing:
                    comps.append(g)

        _group_effects(comps, query.lower())
        _detect_questions(query.lower(), service, comps)
        return Decomposition(query=query, service=service.name, components=comps)


decomposer_registry.add("termite", lambda **kw: TermiteDecomposer(**kw))
