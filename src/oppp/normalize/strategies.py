"""Concrete misspelling-normalization strategies.

These are options to evaluate (docs flag the final choice as undecided), wired
behind the common interface:

  * noop  — passthrough baseline (default).
  * fuzzy — closed-vocab only: bridge a typo to the nearest taxonomy entry via
            rapidfuzz; conservative no-op on open fields (no vocabulary to anchor).
"""

from __future__ import annotations

from oppp.normalize.base import NormalizationResult, normalizer_registry
from oppp.taxonomy.index import TAXONOMY_FILES, get_index

# Which taxonomy a closed-vocab field resolves against (field -> taxonomy name).
FIELD_TO_TAXONOMY: dict[str, str] = {
    "drugs": "drugs",
    "drugsFuzzy": "drugs",
    "effects": "effects",
    "indications": "indications",
    "species": "species",
    "route": "route",
    "documentSource": "sources",
    "sources": "sources",
    "toxicityParameter": "toxicity_parameters",
    "doseType": "dose_type",
    "documentYear": "document_year",
}


class NoOpNormalizer:
    def normalize(self, fragment: str, *, field: str, bucket: str) -> NormalizationResult:
        return NormalizationResult(normalized=fragment, changed=False, confidence=1.0)


class FuzzyNormalizer:
    """Correct closed-vocab fragments toward the nearest taxonomy entry."""

    def __init__(self, accept: float = 88.0) -> None:
        self.accept = accept

    def normalize(self, fragment: str, *, field: str, bucket: str) -> NormalizationResult:
        taxonomy = FIELD_TO_TAXONOMY.get(field)
        if bucket != "closed" or taxonomy not in TAXONOMY_FILES:
            # Open fields: no vocabulary to anchor to -> stay conservative.
            return NormalizationResult(normalized=fragment, changed=False)

        index = get_index(taxonomy)
        # Never "correct" a fragment that already resolves in the vocabulary — an
        # exact name, a plural of one, OR a class/rollup node (e.g. "rodent", whose
        # node is the parent_name "Rodent", not a leaf row). Without the class/plural
        # guard, fuzzy WRatio over-scored a short fragment that is merely a SUBSTRING
        # of an unrelated entry and rewrote the valid class "rodent" to the opposite
        # term "Not-rodent (unspecified)", breaking Stage-2 class expansion.
        if index.contains(fragment) is not None or index.is_class(fragment):
            return NormalizationResult(normalized=fragment, changed=False, confidence=1.0)

        hits = index.lookup(fragment, match="fuzzy", limit=5, cutoff=70.0)
        if not hits:
            return NormalizationResult(normalized=fragment, changed=False, confidence=0.0)

        best = hits[0]
        if best.score >= self.accept and best.name.lower() != fragment.lower():
            return NormalizationResult(
                normalized=best.name,
                candidates=hits,
                changed=True,
                confidence=best.score / 100.0,
                note=f"'{fragment}' -> '{best.name}' (fuzzy {best.score:.0f})",
            )
        # Below acceptance: keep original but surface candidates for the orchestrator.
        return NormalizationResult(
            normalized=fragment,
            candidates=hits,
            changed=False,
            confidence=best.score / 100.0,
            note=f"low-confidence candidates for '{fragment}'",
        )


normalizer_registry.add("noop", lambda **_: NoOpNormalizer())
normalizer_registry.add("fuzzy", lambda **kw: FuzzyNormalizer(**kw))
