from dataclasses import FrozenInstanceError

import pytest

from tests.expectations.test_comparison_interpretations import _comparisons
from tpstudio.expectations import (
    ComparisonJustificationElementKind as Kind,
    ComparisonJustificationExpectationSet, ComparisonJustificationRequirement as Requirement,
    ExpectedComparisonJustification, ExpectedComparisonJustificationElement,
)


def _element(identifier="en", kind=Kind.NORMALIZED_ERROR_VALUE, requirement=Requirement.REQUIRED, phrases=("En =",), group=None, description=" note "):
    return ExpectedComparisonJustificationElement(identifier, kind, requirement, phrases, group, description)


def test_enum_values_are_exact() -> None:
    assert tuple(item.value for item in Kind) == ("normalized_error_value", "threshold_reference", "coherence_classification", "uncertainty_reference", "method_limitation", "experimental_bias", "measurement_limitation")
    assert tuple(item.value for item in Requirement) == ("required", "optional", "one_of_group")


def test_element_preserves_values_order_and_is_frozen() -> None:
    item = _element(phrases=[" E_n = ", "En ="])
    assert item.phrases == (" E_n = ", "En =") and item.description == " note "
    with pytest.raises(FrozenInstanceError): item.description = "x"


@pytest.mark.parametrize("phrases", ["En", b"En", (), ("",), (" ",), ("En", "En")])
def test_invalid_phrase_collections_are_rejected(phrases) -> None:
    with pytest.raises((TypeError, ValueError)): _element(phrases=phrases)


def test_requirement_and_alternative_group_rules() -> None:
    with pytest.raises((TypeError, ValueError)): _element(requirement=Requirement.ONE_OF_GROUP)
    with pytest.raises(ValueError): _element(group="g")
    assert _element(requirement=Requirement.ONE_OF_GROUP, group=" g ").alternative_group == " g "


def test_expectation_rejects_ids_phrases_and_small_groups() -> None:
    element = _element()
    with pytest.raises(ValueError): ExpectedComparisonJustification(" ", (element,))
    with pytest.raises(ValueError): ExpectedComparisonJustification("comparison", (element, element))
    other = _element("other", Kind.THRESHOLD_REFERENCE, phrases=("En =",))
    with pytest.raises(ValueError): ExpectedComparisonJustification("comparison", (element, other))
    grouped = _element("g1", requirement=Requirement.ONE_OF_GROUP, group="g")
    with pytest.raises(ValueError): ExpectedComparisonJustification("comparison", (grouped,))


def test_multiple_kinds_and_valid_group_are_preserved() -> None:
    first = _element()
    a = _element("method", Kind.METHOD_LIMITATION, Requirement.ONE_OF_GROUP, ("méthode",), "limits")
    b = _element("bias", Kind.EXPERIMENTAL_BIAS, Requirement.ONE_OF_GROUP, ("biais",), "limits")
    expected = ExpectedComparisonJustification("comparison", [first, a, b], " exact ")
    assert expected.elements == (first, a, b) and expected.description == " exact "


def test_expectation_set_api_order_partial_coverage_and_unknown() -> None:
    comparisons = _comparisons(two=True)
    first = ExpectedComparisonJustification("comparison", (_element(),))
    second = ExpectedComparisonJustification("comparison2", (_element("x"),))
    expectations = ComparisonJustificationExpectationSet(comparisons, [second, first])
    assert tuple(expectations) == (second, first) and expectations.get("comparison") is first
    assert expectations.in_evaluation_order == (first, second)
    assert ComparisonJustificationExpectationSet(comparisons, (first,)).get("comparison2") is None
    with pytest.raises(ValueError): ComparisonJustificationExpectationSet(comparisons, (ExpectedComparisonJustification("unknown", (_element(),)),))
