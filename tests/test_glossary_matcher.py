from tpstudio.glossary.matcher import (
    has_scientific_vocabulary,
    match_terms,
    matched_categories,
    matched_term_ids,
)
from tpstudio.glossary.models import Glossary, ScientificTerm


def _glossary() -> Glossary:
    return Glossary(
        "test",
        "Test",
        (
            ScientificTerm("angle", "angle", "quantity", aliases=("angles",)),
            ScientificTerm("refrac", "réfraction", "phenomenon"),
        ),
    )


def test_matcher_recognizes_accents_aliases_and_source_positions() -> None:
    matches = match_terms("Les angles de réfraction sont mesurés.", _glossary())

    assert [match.term.id for match in matches] == ["angle", "refrac"]
    assert matches[0].matched_text == "angles"
    assert matches[0].source == "angles"
    assert matches[1].start == 14


def test_matcher_deduplicates_terms_and_respects_word_boundaries() -> None:
    matches = match_terms("angle angleur angle", _glossary())

    assert [match.term.id for match in matches] == ["angle"]
    assert matches[0].matched_text == "angle"


def test_matcher_reports_ids_categories_and_presence() -> None:
    glossary = _glossary()
    text = "Un angle de réfraction"

    assert matched_term_ids(text, glossary) == {"angle", "refrac"}
    assert matched_categories(text, glossary) == {"quantity", "phenomenon"}
    assert has_scientific_vocabulary(text, glossary) is True
    assert has_scientific_vocabulary("Une phrase générale.", glossary) is False


def test_matcher_maps_spans_to_original_text_after_normalization() -> None:
    glossary = Glossary(
        "test-offsets",
        "Offsets",
        (ScientificTerm("coeur-optique", "coeur optique", "phenomenon"),),
    )
    text = "  Le Cœur\n   optique est étudié.  "

    match = match_terms(text, glossary)[0]

    assert match.matched_text == "Cœur\n   optique"
    assert text[match.start:match.end] == match.matched_text


def test_longer_overlapping_spelling_takes_precedence() -> None:
    glossary = Glossary(
        "overlap",
        "Recouvrements",
        (
            ScientificTerm("rayon", "rayon", "instrument"),
            ScientificTerm("rayon-lumineux", "rayon lumineux", "instrument"),
        ),
    )

    matches = match_terms("Le rayon lumineux arrive.", glossary)

    assert [match.term.id for match in matches] == ["rayon-lumineux"]
