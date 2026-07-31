from tpstudio.glossary.models import Glossary, ScientificTerm


def test_scientific_term_exposes_canonical_label_and_aliases() -> None:
    term = ScientificTerm("angle", "angle", "quantity", aliases=("angles",))

    assert term.spellings == ("angle", "angles")


def test_glossary_finds_terms_by_identifier() -> None:
    term = ScientificTerm("angle", "angle", "quantity")
    glossary = Glossary("test", "Test", (term,))

    assert glossary.term_by_id("angle") == term
    assert glossary.term_by_id("absent") is None


def test_glossary_rejects_duplicate_term_identifiers() -> None:
    import pytest

    with pytest.raises(ValueError, match="uniques"):
        Glossary(
            "duplicates",
            "Doublons",
            (
                ScientificTerm("angle", "angle", "quantity"),
                ScientificTerm("angle", "angles", "quantity"),
            ),
        )
