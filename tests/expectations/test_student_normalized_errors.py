from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from tpstudio.expectations import (
    EvaluationBasis, ExpectedQuantity, ExpectedQuantityComparison,
    ExpectedStudentNormalizedError, QuantityComparisonExpectationSet,
    QuantityExpectationSet, ScientificProductionKind, ScientificProductionPlan,
    ScientificProductionSpec, StudentNormalizedErrorExpectationSet,
)


def _comparisons(two=False):
    left = ScientificProductionSpec("left", "Left", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    right = ScientificProductionSpec("right", "Right", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    first = ScientificProductionSpec("comparison", "Comparison", ScientificProductionKind.COMPARISON, (EvaluationBasis.CROSS_PRODUCTION,), depends_on=("left", "right"))
    productions = [left, right, first]
    declared = [ExpectedQuantityComparison("comparison", "left", "right")]
    if two:
        productions.append(ScientificProductionSpec("comparison2", "Comparison 2", ScientificProductionKind.COMPARISON, (EvaluationBasis.CROSS_PRODUCTION,), depends_on=("left", "right")))
        declared.append(ExpectedQuantityComparison("comparison2", "left", "right"))
    plan = ScientificProductionPlan("p", "Plan", tuple(productions))
    quantities = QuantityExpectationSet(plan, (ExpectedQuantity("left", "x", canonical_unit="m"), ExpectedQuantity("right", "y", canonical_unit="m")))
    return QuantityComparisonExpectationSet(plan, quantities, tuple(declared))


def _expected(identifier="comparison", labels=("E_n", "En", "Eₙ"), tolerance=Decimal("0.1"), description=" note "):
    return ExpectedStudentNormalizedError(identifier, labels, tolerance, description)


def test_expectation_is_immutable_and_preserves_exact_values() -> None:
    expected = _expected(labels=[" E_n ", "En"])
    assert expected.labels == (" E_n ", "En")
    assert expected.description == " note "
    with pytest.raises(FrozenInstanceError):
        expected.description = "x"


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_comparison_id_is_rejected(value) -> None:
    with pytest.raises(ValueError):
        _expected(identifier=value)


@pytest.mark.parametrize("labels", [(), [], ("",), ("   ",), ("En", "En")])
def test_invalid_labels_are_rejected(labels) -> None:
    with pytest.raises(ValueError):
        _expected(labels=labels)


@pytest.mark.parametrize("labels", ["En", b"En"])
def test_scalar_string_or_bytes_labels_are_rejected(labels) -> None:
    with pytest.raises(TypeError):
        _expected(labels=labels)


@pytest.mark.parametrize("value", [0, 0.1, "0.1", True])
def test_tolerance_requires_exact_decimal(value) -> None:
    with pytest.raises(TypeError):
        _expected(tolerance=value)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal("-0.1")])
def test_invalid_decimal_tolerance_is_rejected(value) -> None:
    with pytest.raises(ValueError):
        _expected(tolerance=value)


def test_zero_tolerance_is_valid() -> None:
    assert _expected(tolerance=Decimal("0")).absolute_tolerance == 0


def test_expectation_set_validation_and_api() -> None:
    comparisons = _comparisons(two=True)
    first = _expected()
    expectation_set = StudentNormalizedErrorExpectationSet(comparisons, [first])
    assert tuple(expectation_set) == (first,)
    assert len(expectation_set) == 1
    assert expectation_set.get("comparison") is first
    assert expectation_set.get("comparison2") is None
    assert expectation_set.in_evaluation_order == (first,)
    with pytest.raises(FrozenInstanceError):
        expectation_set.expectations = ()
    with pytest.raises(ValueError):
        StudentNormalizedErrorExpectationSet(comparisons, ())
    with pytest.raises(ValueError):
        StudentNormalizedErrorExpectationSet(comparisons, (first, first))
    with pytest.raises(ValueError):
        StudentNormalizedErrorExpectationSet(comparisons, (_expected("unknown"),))


def test_evaluation_order_follows_comparison_plan_not_declaration() -> None:
    comparisons = _comparisons(two=True)
    first = _expected()
    second = _expected("comparison2")
    expectation_set = StudentNormalizedErrorExpectationSet(comparisons, (second, first))
    assert expectation_set.expectations == (second, first)
    assert expectation_set.in_evaluation_order == (first, second)
