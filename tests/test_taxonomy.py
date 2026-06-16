from oppp.taxonomy import get_index


def test_exact_and_singular_lookup():
    sp = get_index("species")
    assert sp.lookup("human")[0].name == "Human"
    assert sp.lookup("rats")[0].name == "Rat"  # naive singularization


def test_fuzzy_corrects_typo():
    dr = get_index("drugs")
    hits = dr.lookup("suntinib")
    assert hits and hits[0].name == "Sunitinib"
    assert hits[0].match == "fuzzy"


def test_class_expansion():
    sp = get_index("species")
    assert sp.is_class("Rodent")
    members = {h.name for h in sp.expand_children("Rodent")}
    assert "Mouse" in members and "Rat" in members
