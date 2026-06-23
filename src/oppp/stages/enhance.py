"""Stage 0 — query enhancement (optional, runs before decomposition).

An enhancer reads the raw NL query and returns an :class:`EnhancedQuery`: the
text the decomposer should read plus structured entity annotations. It must NOT
decompose or build queries — its only job is to make the query easier for the
decomposer to read (e.g. resolving synonyms/brand names to preferred labels).

Backends (pluggable by name):
  * noop    — returns the query unchanged (default; fully offline).
  * termite — SciBite TERMite NER; appends a recognized-entities hints block to
              the query text and records the annotations. Optional (needs the
              SciBite toolkit + TERMITE_* creds).
"""

from __future__ import annotations

from typing import Protocol

from oppp.models import EnhancedQuery, EntityAnnotation
from oppp.registry import Registry
from oppp.services.base import ServiceConfig, get_service


class Enhancer(Protocol):
    def enhance(self, query: str, service: ServiceConfig) -> EnhancedQuery: ...


enhancer_registry: Registry[Enhancer] = Registry("enhancer")


def get_enhancer(name: str = "noop", **kwargs) -> Enhancer:
    return enhancer_registry.create(name, **kwargs)


def enhance(query: str, service: str = "safety", backend: str = "noop") -> EnhancedQuery:
    """Convenience: run Stage 0 with the named backend."""
    return get_enhancer(backend).enhance(query, get_service(service))


# ---------------------------------------------------------------------------
# No-op (default, offline)
# ---------------------------------------------------------------------------
class NoopEnhancer:
    """Pass the query through untouched. The decomposer reads the raw question."""

    def enhance(self, query: str, service: ServiceConfig) -> EnhancedQuery:
        return EnhancedQuery(text=query, annotations=[], source="noop")


enhancer_registry.add("noop", lambda **kw: NoopEnhancer(**kw))


# ---------------------------------------------------------------------------
# TERMite (SciBite NER) enhancer
# ---------------------------------------------------------------------------
# PP TERMite vocabulary id -> a coarse entity type label (for the hints block).
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


class TermiteEnhancer:
    """Annotate entities with SciBite TERMite and attach them as decomposer hints.

    TERMite resolves synonyms, brand names, and variants to preferred labels
    (e.g. 'homo sapiens' -> Human, 'Columvi' -> Glofitamab) which a plain reader
    cannot. The recognized entities are appended to the query text as a hints
    block so the (vocab-free) decomposer can use them, and returned as structured
    annotations for auditing.

    Needs the SciBite toolkit and TERMITE_* credentials in .env (lazy).
    """

    def __init__(self) -> None:
        from oppp.config import get_settings, load_dotenv_if_present

        load_dotenv_if_present()
        s = get_settings()
        if not (s.termite_home and s.termite_client_name and s.termite_client_secret):
            raise RuntimeError(
                "termite enhancer needs TERMITE_HOME/AUTH_URL/CLIENT_NAME/"
                "CLIENT_SECRET in .env (use enhancer='noop' to run offline)."
            )
        try:
            from scibite_toolkit import termite7
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("install the SciBite toolkit to use the termite enhancer") from e

        self._builder_factory = termite7.Termite7RequestBuilder
        self._cfg = s

    def _annotate(self, query: str, vocabs: list[str]):
        b = self._builder_factory()
        b.set_token_url(self._cfg.termite_auth_url)
        b.set_url(self._cfg.termite_home)
        b.set_oauth2(self._cfg.termite_client_name, self._cfg.termite_client_secret)
        return b.annotate_text(text=query, vocabulary=vocabs)

    def enhance(self, query: str, service: ServiceConfig) -> EnhancedQuery:
        annotation = self._annotate(query, list(TERMITE_VOCAB_TO_TYPE))

        seen: set[tuple[str, str]] = set()
        annotations: list[EntityAnnotation] = []
        for group in (annotation or {}).get("included", []) or []:
            for ent in group.get("entities", []) or []:
                etype = TERMITE_VOCAB_TO_TYPE.get(ent.get("vocabularyId"))
                name = (ent.get("name") or "").strip()
                surface = (ent.get("originalText") or name).strip()
                if not name:
                    continue
                key = (name.lower(), etype or "")
                if key in seen:
                    continue
                seen.add(key)
                # TERMite's full equivalent-term set (brand/scientific/abbrev/variants);
                # deduped and excluding the preferred label so Stage 2 can ground the
                # whole [label, *synonyms] pool against the controlled vocabulary.
                synonyms: list[str] = []
                syn_seen = {name.lower()}
                for syn in ent.get("publicSynonyms") or []:
                    syn = (syn or "").strip()
                    if syn and syn.lower() not in syn_seen:
                        syn_seen.add(syn.lower())
                        synonyms.append(syn)
                annotations.append(
                    EntityAnnotation(
                        surface=surface or name,
                        label=name,
                        entity_type=etype,
                        synonyms=synonyms,
                    )
                )

        text = query
        if annotations:
            hints = "; ".join(f"{a.entity_type or 'ENTITY'}: {a.label}" for a in annotations)
            text = f"{query}\n\n[Recognized entities — {hints}]"
        return EnhancedQuery(text=text, annotations=annotations, source="termite")


enhancer_registry.add("termite", lambda **kw: TermiteEnhancer(**kw))
