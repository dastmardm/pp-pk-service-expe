"""Misspelling normalizer behaviour (offline).

Regression guard for the bug where the `fuzzy` normalizer rewrote a valid species
*class* term ("rodent") to the opposite term "Not-rodent (unspecified)" — because
its no-op guard only checked exact leaf rows, while "Rodent" is a parent/class node.
The normalizer must never alter a fragment that already resolves in the vocabulary
(exact name, a plural of one, or a class/rollup node); it must still fix real typos.
"""

from __future__ import annotations

from oppp.models import Component, ComponentType
from oppp.normalize.base import get_normalizer
from oppp.stages.translate import translate_one


def test_fuzzy_leaves_class_term_untouched():
    # "rodent" is a class node (parent_name), not a leaf row -> must not be "corrected".
    res = get_normalizer("fuzzy").normalize("rodent", field="species", bucket="closed")
    assert res.normalized == "rodent"
    assert res.changed is False


def test_fuzzy_leaves_plural_and_exact_untouched():
    fz = get_normalizer("fuzzy")
    assert (
        fz.normalize("rats", field="species", bucket="closed").changed is False
    )  # plural of "Rat"
    assert fz.normalize("Human", field="species", bucket="closed").changed is False  # exact


def test_fuzzy_still_corrects_a_real_typo():
    res = get_normalizer("fuzzy").normalize("Sunitnib", field="drugsFuzzy", bucket="closed")
    assert res.changed is True
    assert res.normalized == "Sunitinib"


def test_rodent_class_resolves_to_class_label_through_fuzzy_normalizer():
    # End-to-end Stage 2: the reported bug was "rodent" collapsing to a junk fuzzy hit
    # ("Not-rodent (unspecified)"). It must resolve as the species CLASS. We emit the
    # class label ("Rodent") rather than inlining every member: the API resolves the
    # label server-side to the identical member set (verified: species="Rodent" and
    # species=[14 members] both return 344917), and inlining large classes busts the
    # API's per-MATCH-list cap. So the contract is "class label", not a member list.
    comp = Component(field="species", nl_fragment="rodent", type=ComponentType.FILTER, reason="x")
    sq = translate_one(comp, "safety", "fuzzy", llm_select=False)
    assert sq.grounding is not None and sq.grounding.expanded_from == "class"
    assert sq.value == "Rodent"
    assert "Not-rodent" not in str(sq.value)
