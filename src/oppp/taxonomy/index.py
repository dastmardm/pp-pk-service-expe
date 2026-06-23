"""In-memory index over a taxonomy CSV: exact/fuzzy lookup + hierarchy expansion.

This is the authoritative source for closed-vocabulary field values. It backs
both grounding (Stage 2) and the offline gazetteer decomposer (Stage 1).

Supported CSV schemas (auto-detected from the header):
  * hierarchical:  name,id,parent_id,parent_name
  * flat/counted:  name,id,count
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from rapidfuzz import fuzz, process

from oppp.config import get_settings
from oppp.models import GroundingHit

# Irregular plurals that a trailing-"s" strip can't singularize. The domain
# regulars ("rats" -> "rat") are handled generically; these are the exceptions
# that otherwise get silently dropped (e.g. "mice" must not become "mic").
_IRREGULAR_PLURALS = {
    "mice": "mouse",
    "lice": "louse",
    "geese": "goose",
    "feet": "foot",
    "teeth": "tooth",
    "oxen": "ox",
    "children": "child",
}


# High-frequency, low-information tokens that would pull unrelated rows into an
# LLM candidate window (every '…test', '…positive', '…assay' entry). Dropped when
# picking the *distinctive* tokens of a phrase so the window stays on-topic.
_WINDOW_STOPWORDS = {
    "test", "tests", "positive", "negative", "assay", "assays", "effect", "effects",
    "level", "levels", "result", "results", "abnormal", "normal", "increased",
    "decreased", "disorder", "disorders", "disease", "diseases", "syndrome",
}


def singular_candidates(term: str) -> list[str]:
    """Singular forms to try for a (possibly plural) term, most-specific first.

    Covers irregular plurals plus the regular "-ies"/"-es"/"-s" suffixes. The
    original term is not included; callers try the exact term themselves first.
    """
    low = term.strip().lower()
    out: list[str] = []
    if low in _IRREGULAR_PLURALS:
        out.append(_IRREGULAR_PLURALS[low])
    if low.endswith("ies") and len(low) > 3:  # "studies" -> "study"
        out.append(term[:-3] + "y")
    if low.endswith("es") and len(low) > 2:  # "boxes" -> "box"
        out.append(term[:-2])
    if low.endswith("s") and len(low) > 1:  # "rats" -> "rat"
        out.append(term[:-1])
    return out


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
        # singularization helps "rats" -> "Rat" and "mice" -> "Mouse"
        for sing in singular_candidates(term):
            hit = self.get_exact(sing)
            if hit is not None:
                return [self._hit(hit, score=98.0, match="exact")]
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

    def candidate_window(self, term: str, *, cap: int = 80) -> list[str]:
        """A focused slice of the closed set for an LLM to search when fuzzy is empty.

        We cannot hand a 12k-row vocabulary to the model, so this builds the rows it
        should *look at*: every entry containing a distinctive token-prefix of the
        phrase (so 'Mutagenicity' surfaces the 'Mutagenic…' rows, 'Ames Test' the
        bacterial-reverse-mutation rows — matches a plain substring search can't reach
        from the inflected/abbreviated phrase), unioned with the fuzzy top-N for
        spelling drift. High-frequency, non-distinctive tokens are dropped so the
        window stays on-topic rather than pulling every row that merely says 'test'.
        For a small vocabulary the prefix scan naturally returns most/all of it.

        The window is only a *retrieval aid*: whatever the LLM picks from it is still
        re-grounded against the CSV, so correctness never depends on the window being
        complete — only on it containing the right rows.
        """
        toks = [t for t in re.findall(r"[a-z0-9]+", term.lower()) if len(t) >= 4]
        toks = [t for t in toks if t not in _WINDOW_STOPWORDS]
        toks.sort(key=len, reverse=True)
        out: list[str] = []
        seen: set[str] = set()
        for t in toks[:2]:  # the two most distinctive tokens
            stem = t[:6]
            for e in self.entries:
                low = e.name.lower()
                if stem in low and low not in seen:
                    seen.add(low)
                    out.append(e.name)
        for h in self.lookup(term, match="fuzzy", limit=20):
            if h.name.lower() not in seen:
                seen.add(h.name.lower())
                out.append(h.name)
        return out[:cap]

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
        return self.class_label(name) is not None

    def class_label(self, name: str) -> str | None:
        """Canonical (CSV-cased) class label for `name`, or None if it's not a class.

        A class is any value that appears as a `parent_name` (it has children),
        tried as given then via singular forms ('Monkeys' -> 'Monkey'), so plural /
        lowercase user phrasings still resolve. Returns the label exactly as it is
        spelled in the taxonomy so it round-trips to the API.
        """
        for cand in (name, *singular_candidates(name)):
            members = self._children.get(cand.strip().lower())
            if members:
                # Prefer the child's stored parent_name (canonical casing); fall back
                # to a matching own-row name, else the candidate as given.
                pn = members[0].parent_name
                if pn:
                    return pn
                own = self._by_name.get(cand.strip().lower())
                return own.name if own else cand
        # Colloquial group with no own node ('Monkeys' — the taxonomy parent is
        # 'Primate'): if the (singularised) term is a word inside several entries that
        # ALL share one parent, that parent is the intended class. The single-parent
        # guard avoids ambiguous words ('rat' spans Rodent/Mollusc/Marsupial -> skip).
        return self._common_parent_for_substring(name)

    def _common_parent_for_substring(self, name: str) -> str | None:
        # If the term (or a singular form) is itself an exact taxonomy entry, it is a
        # specific value ('Mouse', 'Rat'), not a colloquial group — never widen it to a
        # parent class. Only genuinely unmatched plurals ('Monkeys') reach the parent rule.
        if self.get_exact(name) is not None or any(
            self.get_exact(s) is not None for s in singular_candidates(name)
        ):
            return None
        sings = [name.strip().lower(), *[s.lower() for s in singular_candidates(name)]]
        sings = [s for s in dict.fromkeys(sings) if len(s) >= 4]  # skip tiny tokens
        if not sings:
            return None
        parents: set[str] = set()
        matched = 0
        for e in self.entries:
            nm = e.name.lower()
            # word-boundary-ish: the singular term appears as a standalone word
            if any(re.search(rf"\b{re.escape(s)}\b", nm) for s in sings):
                if not e.parent_name:
                    return None  # a matched entry with no parent -> not a clean class
                parents.add(e.parent_name)
                matched += 1
        if matched >= 2 and len(parents) == 1:
            return next(iter(parents))
        return None

    def class_hit(self, class_label: str) -> GroundingHit:
        """A GroundingHit representing a class node by its label.

        The API resolves a class label server-side to its whole member set, so we
        emit the single label rather than inlining children. If the class also has
        its own taxonomy row we carry its id/parent; otherwise (the label exists only
        as a `parent_name`) we still emit the label as a class hit.
        """
        own = self.get_exact(class_label)
        if own is not None:
            return self._hit(own, score=100.0, match="class")
        return GroundingHit(name=class_label, score=100.0, match="class")

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
        """Exact phrase membership for gazetteer matching (incl. plural forms)."""
        e = self.get_exact(phrase)
        if e is not None:
            return e
        for sing in singular_candidates(phrase):
            e = self.get_exact(sing)
            if e is not None:
                return e
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
