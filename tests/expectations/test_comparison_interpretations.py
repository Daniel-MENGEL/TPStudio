from dataclasses import FrozenInstanceError

import pytest

from tpstudio.expectations import (
    ComparisonInterpretationExpectationSet, ComparisonInterpretationKind as Kind,
    EvaluationBasis, ExpectedComparisonInterpretation, ExpectedQuantity,
    ExpectedQuantityComparison, QuantityComparisonExpectationSet,
    QuantityExpectationSet, ScientificProductionKind, ScientificProductionPlan,
    ScientificProductionSpec,
)


def _comparisons(two=False):
    left = ScientificProductionSpec("left", "Left", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    right = ScientificProductionSpec("right", "Right", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    comparison = ScientificProductionSpec("comparison", "Comparison", ScientificProductionKind.COMPARISON, (EvaluationBasis.CROSS_PRODUCTION,), depends_on=("left", "right"))
    productions = [left, right, comparison]
    declared = [ExpectedQuantityComparison("comparison", "left", "right")]
    if two:
        productions.append(ScientificProductionSpec("comparison2", "Comparison 2", ScientificProductionKind.COMPARISON, (EvaluationBasis.CROSS_PRODUCTION,), depends_on=("left", "right")))
        declared.append(ExpectedQuantityComparison("comparison2", "left", "right"))
    plan = ScientificProductionPlan("p", "Plan", tuple(productions))
    quantities = QuantityExpectationSet(plan, (ExpectedQuantity("left", "x", canonical_unit="m"), ExpectedQuantity("right", "y", canonical_unit="m")))
    return QuantityComparisonExpectationSet(plan, quantities, tuple(declared))


def _expected(identifier="comparison", phrases=((Kind.COHERENT, " Résultats cohérents "),), description=" note "):
    return ExpectedComparisonInterpretation(identifier, phrases, description)


def test_enum_values_are_exact() -> None:
    assert tuple(item.value for item in Kind) == ("coherent", "incoherent", "strongly_incoherent", "method_limitation")


def test_exact_values_order_and_immutability_are_preserved() -> None:
    item = _expected(phrases=[(Kind.INCOHERENT, "écart"), (Kind.COHERENT, "Écart")])
    assert item.phrases == ((Kind.INCOHERENT, "écart"), (Kind.COHERENT, "Écart"))
    assert item.description == " note "
    with pytest.raises(FrozenInstanceError):
        item.description = "x"


@pytest.mark.parametrize("identifier", ["", "  "])
def test_blank_identifier_is_rejected(identifier) -> None:
    with pytest.raises(ValueError):
        _expected(identifier)


@pytest.mark.parametrize("phrases", ["x", b"x", (), [], ((Kind.COHERENT, ""),), ((Kind.COHERENT, "  "),)])
def test_invalid_phrase_collections_are_rejected(phrases) -> None:
    with pytest.raises((TypeError, ValueError)):
        _expected(phrases=phrases)


@pytest.mark.parametrize("entry", [[Kind.COHERENT, "x"], (Kind.COHERENT,), ("coherent", "x"), (Kind.COHERENT, 1)])
def test_invalid_entries_are_rejected(entry) -> None:
    with pytest.raises(TypeError):
        _expected(phrases=(entry,))


def test_duplicate_literal_even_across_kinds_is_rejected() -> None:
    with pytest.raises(ValueError):
        _expected(phrases=((Kind.COHERENT, "x"), (Kind.INCOHERENT, "x")))


def test_set_api_partial_coverage_and_evaluation_order() -> None:
    comparisons = _comparisons(two=True)
    first, second = _expected(), _expected("comparison2")
    items = ComparisonInterpretationExpectationSet(comparisons, [second, first])
    assert tuple(items) == (second, first) and len(items) == 2
    assert items.get("comparison") is first
    assert items.in_evaluation_order == (first, second)
    partial = ComparisonInterpretationExpectationSet(comparisons, (first,))
    assert partial.get("comparison2") is None


def test_set_rejects_empty_duplicate_and_unknown_expectations() -> None:
    comparisons = _comparisons()
    with pytest.raises(ValueError):
        ComparisonInterpretationExpectationSet(comparisons, ())
    item = _expected()
    with pytest.raises(ValueError):
        ComparisonInterpretationExpectationSet(comparisons, (item, item))
    with pytest.raises(ValueError):
        ComparisonInterpretationExpectationSet(comparisons, (_expected("unknown"),))
