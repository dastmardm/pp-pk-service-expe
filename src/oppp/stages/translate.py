"""Stage 2 — per-field translation. One component -> one machine subquery.

Closed-vocab fields are grounded against the taxonomy CSV (with hierarchy
expansion); open fields produce REGEX/MATCH directly; enums and booleans map to
fixed values. A pluggable normalizer runs first to absorb misspellings.
"""

from __future__ import annotations

import re

from oppp.models import (
    Component,
    ComponentType,
    Grounding,
    GroundingHit,
    MachineSubquery,
    Operator,
)
from oppp.normalize.base import Normalizer, get_normalizer
from oppp.services.base import ServiceConfig, get_service
from oppp.taxonomy.index import get_index

# Open fields searched as free-text substrings rather than exact values.
_REGEX_OPEN_FIELDS = {"studyGroup", "ages"}

# Minimal synonym expansion for free-text study-group conditions (extensible).
_STUDYGROUP_SYNONYMS: dict[str, list[str]] = {
    "hepatic impairment": [
        "cirrhosis", "liver disease", "hepatic insufficiency", "hepatic impairment",
        "liver impairment", "Child-Pugh B", "Child-Pugh C", "liver failure",
        "hepatic failure", "liver insufficiency", "hepatic disease",
    ],
    "renal impairment": [
        "renal impairment", "renal insufficiency", "kidney disease", "renal failure",
        "chronic kidney disease", "CKD",
    ],
}


def translate_one(
    component: Component, service: str = "safety", normalizer: str = "noop"
) -> MachineSubquery | None:
    """Convenience wrapper resolving service + normalizer by name."""
    return translate_component(component, get_service(service), get_normalizer(normalizer))


def translate_component(
    component: Component, service: ServiceConfig, normalizer: Normalizer | None = None
) -> MachineSubquery | None:
    """Translate a single FILTER component. Returns None for QUESTION components."""
    if component.type is ComponentType.QUESTION:
        return None
    normalizer = normalizer or get_normalizer("noop")
    spec = service.spec(component.field)
    frag = component.nl_fragment.strip()

    if spec is None:
        return MachineSubquery(
            field=component.field, operator=Operator.MATCH, value=frag,
            boolean_group=component.boolean_group, notes="no field spec; raw value",
        )

    if spec.bucket == "closed" and spec.taxonomy:
        return _translate_closed(component, spec, service, normalizer)
    if spec.bucket == "boolean":
        return _translate_boolean(component, spec)
    if spec.bucket == "enum":
        return _translate_enum(component, spec)
    return _translate_open(component, spec)


# ---------------------------------------------------------------------------
def _translate_closed(component, spec, service, normalizer) -> MachineSubquery:
    index = get_index(spec.taxonomy)
    frag = component.nl_fragment.strip()

    # documentYear: numeric thresholds -> RANGE / MATCH.
    if spec.taxonomy == "document_year":
        return _translate_year(component, spec)

    norm = normalizer.normalize(frag, field=component.field, bucket="closed")
    term = norm.normalized

    expanded_from = None
    if index.is_class(term):
        hits = index.expand_children(term)
        expanded_from = "class"
    else:
        hits = index.lookup(term, match="fuzzy", limit=5)

    if hits:
        values = [h.name for h in hits]
        grounding = Grounding(
            matched=hits[:25], expanded_from=expanded_from,
            confidence=min(1.0, (hits[0].score / 100.0)),
        )
    else:
        values = [term]
        grounding = Grounding(
            matched=[GroundingHit(name=term, match="unmatched", score=0.0)],
            confidence=0.0,
        )

    # Drug-style fuzzy broadening: trailing wildcard on a single leaf term.
    if spec.fuzzy_wildcard and expanded_from is None and len(values) == 1:
        values = [f"{values[0]}*"]

    value = values if len(values) != 1 else values[0]
    note = norm.note if norm.changed else None
    return MachineSubquery(
        field=spec.emit_field, operator=Operator.MATCH, value=value,
        boolean_group=component.boolean_group, entity_name=spec.entity_name,
        grounding=grounding, notes=note,
    )


def _translate_year(component, spec) -> MachineSubquery:
    frag = component.nl_fragment.lower()
    m = re.search(r"(\d{4})", frag)
    year = int(m.group(1)) if m else None
    if year is None:
        return MachineSubquery(field=spec.emit_field, operator=Operator.MATCH, value=frag)
    if any(w in frag for w in ("after", "since", "from", ">")):
        return MachineSubquery(field=spec.emit_field, operator=Operator.RANGE, value={"min": year})
    if any(w in frag for w in ("before", "until", "<")):
        return MachineSubquery(field=spec.emit_field, operator=Operator.RANGE, value={"max": year})
    return MachineSubquery(field=spec.emit_field, operator=Operator.MATCH, value=year)


def _translate_boolean(component, spec) -> MachineSubquery:
    val = str(component.nl_fragment).strip().lower() in ("true", "yes", "1", "preclinical")
    return MachineSubquery(field=spec.emit_field, operator=Operator.MATCH, value=val)


def _translate_enum(component, spec) -> MachineSubquery:
    frag = component.nl_fragment.strip().lower()
    for allowed in spec.enum_values:
        if allowed.lower() == frag:
            return MachineSubquery(field=spec.emit_field, operator=Operator.MATCH, value=allowed)
    return MachineSubquery(
        field=spec.emit_field, operator=Operator.MATCH, value=component.nl_fragment,
        notes="value not in enum allow-list",
    )


def _translate_open(component, spec) -> MachineSubquery:
    frag = component.nl_fragment.strip()
    if spec.name in _REGEX_OPEN_FIELDS:
        key = frag.lower()
        terms = _STUDYGROUP_SYNONYMS.get(key, [frag])
        pattern = ".*(" + "|".join(re.escape(t) for t in terms) + ").*"
        return MachineSubquery(
            field=spec.emit_field, operator=Operator.REGEX, pattern=pattern,
            boolean_group=component.boolean_group, entity_name=spec.entity_name,
        )
    return MachineSubquery(
        field=spec.emit_field, operator=Operator.MATCH, value=frag,
        boolean_group=component.boolean_group, entity_name=spec.entity_name,
    )
