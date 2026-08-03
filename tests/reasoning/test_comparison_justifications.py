import pytest

from tpstudio.expectations import (
    ComparisonJustificationElementKind as Kind,
    ComparisonJustificationRequirement as Requirement,
    ExpectedComparisonJustification, ExpectedComparisonJustificationElement,
)
from tpstudio.reasoning import (
    ComparisonJustificationDetection, ComparisonJustificationObservation,
    LiteralComparisonJustificationExtractor, extract_comparison_justification,
)


def _expectation():
    return ExpectedComparisonJustification("comparison", (
        ExpectedComparisonJustificationElement("en", Kind.NORMALIZED_ERROR_VALUE, Requirement.REQUIRED, ("En =", "En = 5")),
        ExpectedComparisonJustificationElement("threshold", Kind.THRESHOLD_REFERENCE, Requirement.REQUIRED, ("En > 4",)),
    ))


def test_literal_offsets_longest_same_element_and_multiple_elements() -> None:
    detection = extract_comparison_justification("En = 5 et En > 4", _expectation())
    assert tuple((item.element_id, item.phrase, item.start, item.end) for item in detection) == (("en", "En = 5", 0, 6), ("threshold", "En > 4", 10, 16))


def test_case_and_unicode_are_not_normalized() -> None:
    element = ExpectedComparisonJustificationElement("x", Kind.UNCERTAINTY_REFERENCE, Requirement.OPTIONAL, ("Écart",))
    expected = ExpectedComparisonJustification("comparison", (element,))
    assert not extract_comparison_justification("écart écart", expected).has_observations


def test_overlapping_occurrences_at_distinct_offsets_are_preserved() -> None:
    element = ExpectedComparisonJustificationElement("x", Kind.MEASUREMENT_LIMITATION, Requirement.REQUIRED, ("aba",))
    detection = extract_comparison_justification("ababa", ExpectedComparisonJustification("comparison", (element,)))
    assert tuple((item.start, item.end) for item in detection) == ((0, 3), (2, 5))


def test_same_offset_keeps_one_observation_per_element() -> None:
    a = ExpectedComparisonJustificationElement("a", Kind.METHOD_LIMITATION, Requirement.REQUIRED, ("ABCDE",))
    b = ExpectedComparisonJustificationElement("b", Kind.EXPERIMENTAL_BIAS, Requirement.OPTIONAL, ("ABC",))
    detection = LiteralComparisonJustificationExtractor().extract("ABCDE", ExpectedComparisonJustification("comparison", (a, b)))
    assert detection.observed_element_ids == ("b", "a")


def test_detection_queries_unique_ids_kinds_and_source_not_stored() -> None:
    expected = _expectation()
    detection = extract_comparison_justification("En = En = 5 En > 4", expected)
    assert len(detection.for_element("en")) == 2
    assert detection.for_kind(Kind.THRESHOLD_REFERENCE)[0].element_id == "threshold"
    assert detection.observed_element_ids == ("en", "threshold")
    assert detection.observed_kinds == (Kind.NORMALIZED_ERROR_VALUE, Kind.THRESHOLD_REFERENCE)
    assert detection.is_element_observed("en") and not detection.is_element_observed("other")
    assert not hasattr(detection, "text")


def test_observation_and_detection_reject_foreign_identity_and_order() -> None:
    expected = _expectation()
    observation = ComparisonJustificationObservation(expected, expected.elements[0], "En =", 2, 6)
    with pytest.raises(ValueError): ComparisonJustificationDetection(expected, (observation, observation))
    foreign = _expectation()
    with pytest.raises(ValueError): ComparisonJustificationDetection(foreign, (observation,))
