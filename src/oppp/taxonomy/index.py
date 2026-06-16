"""In-memory index over a taxonomy CSV: exact/fuzzy lookup + hierarchy expansion.

This is the authoritative source for closed-vocabulary field values. It backs
both grounding (Stage 2) and the offline gazetteer decomposer (Stage 1).

Supported CSV schemas (auto-detected from the header):
  * hierarchical:  name,id,parent_id,parent_name
  * flat/counted:  name,id,count
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from rapidfuzz import fuzz, process

from oppp.config import get_settings
from oppp.models import GroundingHit


@dataclass
class TaxonomyEntry:
    name: str
    id: str | None = None
    parent_id: str | None = None
    parent_name: str | None = None
    count: int | None = None


@dataclass
class TaxonomyIndex:
    """Loaded taxonomy with lookup + expansion helpers."""

    name: str
    entries: list[TaxonomyEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._by_name: dict[str, TaxonomyEntry] = {}
        self._children: dict[str, list[TaxonomyEntry]] = {}  # parent_name(lower) -> rows
        for e in self.entries:
            self._by_name.setdefault(e.name.lower(), e)
            if e.parent_name:
                self._children.setdefault(e.parent_name.lower(), []).append(e)
        self._names = [e.name for e in self.entries]

    # ----- construction -----------------------------------------------------
    @classmethod
    def from_csv(cls, path: Path, name: str | None = None) -> TaxonomyIndex:
        rows: list[TaxonomyEntry] = []
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                cnt = row.get("count")
                rows.append(
                    TaxonomyEntry(
                        name=(row.get("name") or "").strip(),
                        id=(row.get("id") or None),
                        parent_id=(row.get("parent_id") or None),
                        parent_name=(row.get("parent_name") or None),
                        count=int(cnt) if cnt and cnt.isdigit() else None,
                    )
                )
        return cls(name=name or path.stem, entries=[r for r in rows if r.name])

    # ----- exact / fuzzy lookup ---------------------------------------------
    def get_exact(self, term: str) -> TaxonomyEntry | None:
        return self._by_name.get(term.strip().lower())

    def lookup(
        self, term: str, *, match: str = "fuzzy", limit: int = 10, cutoff: float = 80.0
    ) -> list[GroundingHit]:
        """Resolve a term to taxonomy entries. Exact first, then fuzzy."""
        term = term.strip()
        if not term:
            return []
        exact = self.get_exact(term)
        if exact is not None:
            return [self._hit(exact, score=100.0, match="exact")]
        # naive singularization helps "rats" -> "Rat"
        if term.lower().endswith("s"):
            sing = self.get_exact(term[:-1])
            if sing is not None:
                return [self._hit(sing, score=98.0, match="exact")]
        if match == "exact":
            return []
        scored = process.extract(
            term, self._names, scorer=fuzz.WRatio, limit=limit, score_cutoff=cutoff
        )
        hits: list[GroundingHit] = []
        for matched_name, score, _ in scored:
            entry = self._by_name[matched_name.lower()]
            hits.append(self._hit(entry, score=float(score), match="fuzzy"))
        return hits

    def best_fuzzy(self, term: str, *, cutoff: float = 80.0) -> GroundingHit | None:
        """Single best fuzzy match using fuzz.ratio (tuned for misspelling detection).

        fuzz.ratio cleanly separates typos (~82-91) from unrelated words (<=63),
        unlike WRatio which over-scores substrings. Used by the gazetteer's
        fuzzy detection pass so misspelled entities aren't dropped in Stage 1.
        """
        term = term.strip()
        if not term:
            return None
        m = process.extractOne(term, self._names, scorer=fuzz.ratio, score_cutoff=cutoff)
        if m is None:
            return None
        name, score, _ = m
        return self._hit(self._by_name[name.lower()], score=float(score), match="fuzzy")

    # ----- hierarchy expansion ----------------------------------------------
    def expand_children(self, class_name: str, *, recursive: bool = True) -> list[GroundingHit]:
        """All members under a class node (matched by parent_name)."""
        out: list[GroundingHit] = []
        seen: set[str] = set()
        frontier = [class_name]
        while frontier:
            current = frontier.pop()
            for child in self._children.get(current.strip().lower(), []):
                key = child.name.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(self._hit(child, score=100.0, match="expand"))
                if recursive:
                    frontier.append(child.name)
        return out

    def is_class(self, name: str) -> bool:
        return name.strip().lower() in self._children

    def expand_family(self, term: str) -> list[GroundingHit]:
        """MedDRA-style rollup: a leaf term -> all members of its parent group.

        E.g. 'Neutropenia' (parent 'Neutropenias') -> Agranulocytosis, Febrile
        neutropenia, Granulocytopenia, … (the parent's children, incl. the term).
        Falls back to children if the term is itself a class, else just the term.
        """
        e = self.get_exact(term)
        if e is None:
            return []
        if e.parent_name and e.parent_name.lower() in self._children:
            members = self.expand_children(e.parent_name)
        elif self.is_class(e.name):
            members = self.expand_children(e.name)
        else:
            return [self._hit(e, score=100.0, match="exact")]
        # Roll up to leaf terms only: intermediate category nodes (themselves
        # parents) are not searchable PT values and make the API reject the query.
        leaves = [h for h in members if not self.is_class(h.name)]
        return leaves or members

    # ----- gazetteer (offline NER) ------------------------------------------
    def contains(self, phrase: str) -> TaxonomyEntry | None:
        """Exact phrase membership for gazetteer matching (incl. naive plural)."""
        e = self.get_exact(phrase)
        if e is not None:
            return e
        if phrase.lower().endswith("s"):
            return self.get_exact(phrase[:-1])
        return None

    # ----- helpers -----------------------------------------------------------
    def _hit(self, e: TaxonomyEntry, *, score: float, match: str) -> GroundingHit:
        return GroundingHit(
            name=e.name,
            id=e.id,
            parent_id=e.parent_id,
            parent_name=e.parent_name,
            score=score,
            match=match,
            count=e.count,
        )


# Maps logical taxonomy name -> CSV filename in inputs/.
TAXONOMY_FILES: dict[str, str] = {
    "drugs": "drugs.csv",
    "effects": "effects.csv",
    "indications": "indications.csv",
    "species": "species.csv",
    "route": "route.csv",
    "sources": "sources.csv",
    "toxicity_parameters": "toxicity_parameters.csv",
    "dose_type": "dose_type.csv",
    "document_year": "document_year.csv",
}


@cache
def get_index(taxonomy: str) -> TaxonomyIndex:
    """Load and cache a taxonomy index by logical name."""
    if taxonomy not in TAXONOMY_FILES:
        raise KeyError(f"no taxonomy '{taxonomy}'. known: {sorted(TAXONOMY_FILES)}")
    path = get_settings().inputs_dir / TAXONOMY_FILES[taxonomy]
    return TaxonomyIndex.from_csv(path, name=taxonomy)
