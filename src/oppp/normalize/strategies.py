"""Concrete misspelling-normalization strategies.

Fixed policy (CONST-8):
  * ClosedSetNormalizer  — fuzzy closed-set correction for closed/enum fields
  * DrugNormalizer       — drug-specific normalizer (same fuzzy approach, drug taxonomy)
  * ConservativeNormalizer — conservative surface cleanup for open-set fields

Also registers legacy aliases 'noop' and 'fuzzy' for backward compatibility.
"""

from __future__ import annotations

from oppp.normalize.base import NormalizationResult, normalizer_registry
from oppp.taxonomy.index import TAXONOMY_FILES, get_index

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


class ConservativeNormalizer:
    """Open-set field cleanup: passthrough (no vocabulary to anchor to)."""

    def normalize(self, fragment: str, *, field: str, bucket: str) -> NormalizationResult:
        return NormalizationResult(normalized=fragment, changed=False, confidence=1.0)


class DrugNormalizer:
    """Drug-specific normalizer: fuzzy correction against the drugs taxonomy."""

    def __init__(self, accept: float = 88.0) -> None:
        self.accept = accept

    def normalize(self, fragment: str, *, field: str, bucket: str) -> NormalizationResult:
        index = get_index("drugs")
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
                note=f"'{fragment}' -> '{best.name}' (drug fuzzy {best.score:.0f})",
            )
        return NormalizationResult(
            normalized=fragment,
            candidates=hits,
            changed=False,
            confidence=best.score / 100.0,
        )


class ClosedSetNormalizer:
    """Closed-set fuzzy correction for closed/enum vocabulary fields."""

    def __init__(self, accept: float = 88.0) -> None:
        self.accept = accept

    def normalize(self, fragment: str, *, field: str, bucket: str) -> NormalizationResult:
        taxonomy = FIELD_TO_TAXONOMY.get(field)
        if bucket != "closed" or taxonomy not in TAXONOMY_FILES:
            return NormalizationResult(normalized=fragment, changed=False)

        index = get_index(taxonomy)
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
        return NormalizationResult(
            normalized=fragment,
            candidates=hits,
            changed=False,
            confidence=best.score / 100.0,
            note=f"low-confidence candidates for '{fragment}'",
        )


# Legacy alias: NoOpNormalizer = ConservativeNormalizer for backward compat
NoOpNormalizer = ConservativeNormalizer
# Legacy alias: FuzzyNormalizer = ClosedSetNormalizer for backward compat
FuzzyNormalizer = ClosedSetNormalizer

normalizer_registry.add("noop", lambda **_: ConservativeNormalizer())
normalizer_registry.add("fuzzy", lambda **kw: ClosedSetNormalizer(**kw))
normalizer_registry.add("closed", lambda **kw: ClosedSetNormalizer(**kw))
normalizer_registry.add("open", lambda **_: ConservativeNormalizer())
normalizer_registry.add("drug", lambda **kw: DrugNormalizer(**kw))
