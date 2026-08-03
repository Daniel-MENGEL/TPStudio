from dataclasses import FrozenInstanceError

import pytest

from tpstudio.expectations import ComparisonInterpretationKind as Kind, ExpectedComparisonInterpretation
from tpstudio.reasoning import (
    ComparisonInterpretationDetection, ComparisonInterpretationObservation,
    LiteralComparisonInterpretationExtractor, extract_comparison_interpretation,
)


def _expected(phrases=((Kind.COHERENT, "cohérents"), (Kind.INCOHERENT, "pas cohérents"))):
    return ExpectedComparisonInterpretation("comparison", phrases)


def test_literal_case_sensitive_offsets_and_properties() -> None:
    expected = _expected()
    detection = extract_comparison_interpretation("COHÉRENTS puis cohérents", expected)
    assert detection.unique and not detection.absent and not detection.ambiguous
    assert detection.observations[0].start == 15 and detection.observations[0].end == 24
    assert detection.observed_kinds == (Kind.COHERENT,)
    assert detection.selected_observation is detection.observations[0]


def test_unicode_is_not_normalized() -> None:
    expected = _expected(((Kind.COHERENT, "é"),))
    assert extract_comparison_interpretation("é", expected).absent


def test_longest_phrase_wins_at_same_offset() -> None:
    expected = _expected(((Kind.INCOHERENT, "pas cohérents"), (Kind.COHERENT, "pas")))
    detection = extract_comparison_interpretation("pas cohérents", expected)
    assert detection.unique and detection.observed_kinds == (Kind.INCOHERENT,)


def test_equal_span_uses_declaration_order() -> None:
    expected = _expected(((Kind.COHERENT, "abc"),))
    object.__setattr__(expected, "phrases", (
        (Kind.INCOHERENT, "abc"), (Kind.COHERENT, "abc"),
    ))
    detection = extract_comparison_interpretation("abc", expected)
    assert detection.unique
    assert detection.observed_kinds == (Kind.INCOHERENT,)


def test_distinct_occurrences_are_ambiguous_in_text_order() -> None:
    expected = _expected()
    detection = LiteralComparisonInterpretationExtractor().extract("pas cohérents puis cohérents", expected)
    assert detection.ambiguous and detection.selected_observation is None
    assert tuple(item.start for item in detection.observations) == (0, 4, 19)


def test_overlapping_occurrences_of_same_phrase_are_all_preserved() -> None:
    expected = _expected(((Kind.COHERENT, "aba"),))
    detection = extract_comparison_interpretation("ababa", expected)
    assert tuple((item.start, item.end) for item in detection.observations) == ((0, 3), (2, 5))
    assert detection.ambiguous
    assert detection.selected_observation is None


def test_overlapping_phrases_at_distinct_offsets_are_all_preserved() -> None:
    expected = _expected(((Kind.COHERENT, "ABCDE"), (Kind.INCOHERENT, "CDEFG")))
    detection = extract_comparison_interpretation("ABCDEFG", expected)
    assert tuple((item.start, item.end) for item in detection.observations) == ((0, 5), (2, 7))
    assert detection.ambiguous


def test_non_overlapping_occurrences_are_both_preserved() -> None:
    expected = _expected(((Kind.COHERENT, "aba"),))
    detection = extract_comparison_interpretation("aba puis aba", expected)
    assert tuple((item.start, item.end) for item in detection.observations) == ((0, 3), (9, 12))
    assert detection.ambiguous


def test_models_validate_identity_order_duplicates_and_are_frozen() -> None:
    expected = _expected()
    observation = ComparisonInterpretationObservation(expected, Kind.COHERENT, "cohérents", 0, 9)
    with pytest.raises(FrozenInstanceError):
        observation.start = 1
    with pytest.raises(ValueError):
        ComparisonInterpretationDetection(expected, (observation, observation))
    foreign = _expected()
    with pytest.raises(ValueError):
        ComparisonInterpretationDetection(foreign, (observation,))


def test_source_text_is_not_stored() -> None:
    detection = extract_comparison_interpretation("cohérents", _expected())
    assert not hasattr(detection, "text") and not hasattr(detection.observations[0], "text")
