from dataclasses import FrozenInstanceError, fields
from decimal import Decimal

import pytest

from tpstudio.expectations import (
    ComparisonPedagogicalContext,
    EvaluationBasis,
    ExpectedQuantity,
    ExpectedQuantityComparison,
    NormalizedErrorThresholds,
    QuantityComparisonExpectationSet,
    QuantityComparisonMethod,
    QuantityExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
)


def _production(identifier, kind, *, depends_on=()):
    return ScientificProductionSpec(
        identifier, identifier, kind, (EvaluationBasis.STRUCTURAL,),
        depends_on=depends_on,
    )


def _context(*, extra_dependency=False, second_comparison=False):
    left = _production("gravity_dynamic", ScientificProductionKind.QUANTITY)
    right = _production("gravity_static", ScientificProductionKind.QUANTITY)
    unused = _production("gravity_unused", ScientificProductionKind.QUANTITY)
    extra = _production("period_plot", ScientificProductionKind.PLOT)
    dependencies = (left.id, right.id, *((extra.id,) if extra_dependency else ()))
    comparison = _production(
        "gravity_comparison", ScientificProductionKind.COMPARISON,
        depends_on=dependencies,
    )
    productions = [left, right, unused, extra, comparison]
    if second_comparison:
        productions.append(_production(
            "gravity_comparison_reverse", ScientificProductionKind.COMPARISON,
            depends_on=(right.id, left.id),
        ))
    plan = ScientificProductionPlan("pendulum", "Pendule", tuple(productions))
    quantities = QuantityExpectationSet(plan, (
        ExpectedQuantity(left.id, "g", canonical_unit="m·s⁻²"),
        ExpectedQuantity(right.id, "g", canonical_unit="m·s⁻²"),
        ExpectedQuantity(unused.id, "g", canonical_unit="m·s⁻²"),
    ))
    return plan, quantities


def _comparison(
    production_id="gravity_comparison",
    left="gravity_dynamic",
    right="gravity_static",
    *,
    context=ComparisonPedagogicalContext.OPEN,
):
    return ExpectedQuantityComparison(
        production_id, left, right,
        pedagogical_context=context,
    )


def _set(*comparisons, context=None):
    plan, quantities = context or _context(second_comparison=len(comparisons) > 1)
    return QuantityComparisonExpectationSet(
        plan, quantities, comparisons or (_comparison(),)
    )


def test_enum_values_are_exact_and_limited() -> None:
    assert tuple(item.value for item in QuantityComparisonMethod) == (
        "normalized_error",
    )
    assert tuple(item.value for item in ComparisonPedagogicalContext) == (
        "open", "coherence_expected", "incoherence_possible",
        "method_limitation_expected",
    )


def test_default_thresholds_are_exact_decimals_and_models_are_immutable() -> None:
    thresholds = NormalizedErrorThresholds()
    comparison = _comparison()
    expectation_set = _set(comparison)
    assert thresholds.coherence_limit == Decimal("2")
    assert thresholds.strong_incoherence_limit == Decimal("4")
    assert type(thresholds.coherence_limit) is Decimal
    assert comparison.thresholds == thresholds
    for instance, attribute in (
        (thresholds, "coherence_limit"),
        (comparison, "context_note"),
        (expectation_set, "comparisons"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(instance, attribute, None)


@pytest.mark.parametrize("value", [2, 2.0, "2", True])
@pytest.mark.parametrize("field_name", ["coherence_limit", "strong_incoherence_limit"])
def test_thresholds_require_exact_decimals(field_name, value) -> None:
    values = {"coherence_limit": Decimal("2"), "strong_incoherence_limit": Decimal("4")}
    values[field_name] = value
    with pytest.raises(TypeError):
        NormalizedErrorThresholds(**values)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
@pytest.mark.parametrize("field_name", ["coherence_limit", "strong_incoherence_limit"])
def test_thresholds_reject_non_finite_decimals(field_name, value) -> None:
    values = {"coherence_limit": Decimal("2"), "strong_incoherence_limit": Decimal("4")}
    values[field_name] = value
    with pytest.raises(ValueError, match="finis"):
        NormalizedErrorThresholds(**values)


@pytest.mark.parametrize(
    ("coherence", "strong"),
    [
        (Decimal("0"), Decimal("4")),
        (Decimal("-1"), Decimal("4")),
        (Decimal("2"), Decimal("0")),
        (Decimal("2"), Decimal("-4")),
        (Decimal("2"), Decimal("2")),
        (Decimal("4"), Decimal("2")),
    ],
)
def test_thresholds_reject_non_positive_equal_or_reversed_values(coherence, strong) -> None:
    with pytest.raises(ValueError):
        NormalizedErrorThresholds(coherence, strong)


def test_custom_thresholds_are_preserved_without_classification_api() -> None:
    thresholds = NormalizedErrorThresholds(Decimal("1.5"), Decimal("3.25"))
    assert thresholds.coherence_limit == Decimal("1.5")
    assert thresholds.strong_incoherence_limit == Decimal("3.25")
    assert not hasattr(thresholds, "evaluate")
    assert not hasattr(thresholds, "classify")
    assert not hasattr(thresholds, "compare")


@pytest.mark.parametrize("field_name", ["production_id", "left_quantity_id", "right_quantity_id"])
@pytest.mark.parametrize("value", ["", "   "])
def test_comparison_rejects_blank_identifiers(field_name, value) -> None:
    values = {
        "production_id": "gravity_comparison",
        "left_quantity_id": "gravity_dynamic",
        "right_quantity_id": "gravity_static",
    }
    values[field_name] = value
    with pytest.raises(ValueError):
        ExpectedQuantityComparison(**values)


def test_comparison_rejects_same_quantity_and_invalid_component_types() -> None:
    with pytest.raises(ValueError, match="distinctes"):
        _comparison(right="gravity_dynamic")
    with pytest.raises(TypeError):
        ExpectedQuantityComparison(1, "left", "right")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ExpectedQuantityComparison("c", "left", "right", method="normalized_error")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ExpectedQuantityComparison("c", "left", "right", thresholds=(2, 4))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ExpectedQuantityComparison("c", "left", "right", pedagogical_context="open")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ExpectedQuantityComparison("c", "left", "right", context_note=1)  # type: ignore[arg-type]


def test_comparison_preserves_all_strings_and_context_exactly() -> None:
    comparison = ExpectedQuantityComparison(
        "  gravity_comparison  ", "  gravity_dynamic  ", "  gravity_static  ",
        pedagogical_context=ComparisonPedagogicalContext.METHOD_LIMITATION_EXPECTED,
        context_note="  La méthode statique est peu fiable.  ",
    )
    assert comparison.production_id == "  gravity_comparison  "
    assert comparison.left_quantity_id == "  gravity_dynamic  "
    assert comparison.right_quantity_id == "  gravity_static  "
    assert comparison.context_note == "  La méthode statique est peu fiable.  "


def test_set_converts_to_tuple_preserves_order_and_basic_api() -> None:
    plan, quantities = _context(second_comparison=True)
    first = _comparison()
    second = _comparison(
        "gravity_comparison_reverse", "gravity_static", "gravity_dynamic"
    )
    expectation_set = QuantityComparisonExpectationSet(
        plan, quantities, [second, first]  # type: ignore[arg-type]
    )
    assert expectation_set.comparisons == (second, first)
    assert tuple(expectation_set) == (second, first)
    assert len(expectation_set) == 2
    assert expectation_set.get(first.production_id) is first
    assert expectation_set.get("unknown") is None


def test_set_rejects_empty_invalid_duplicate_and_incoherent_plan() -> None:
    plan, quantities = _context()
    with pytest.raises(ValueError):
        QuantityComparisonExpectationSet(plan, quantities, ())
    with pytest.raises(TypeError):
        QuantityComparisonExpectationSet(plan, quantities, (object(),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="uniques"):
        QuantityComparisonExpectationSet(plan, quantities, (_comparison(), _comparison()))
    other_plan, _ = _context()
    with pytest.raises(ValueError, match="partager"):
        QuantityComparisonExpectationSet(other_plan, quantities, (_comparison(),))


def test_set_rejects_unknown_or_non_comparison_target() -> None:
    plan, quantities = _context()
    with pytest.raises(ValueError, match="inconnue"):
        QuantityComparisonExpectationSet(plan, quantities, (_comparison("unknown"),))
    with pytest.raises(ValueError, match="COMPARISON"):
        QuantityComparisonExpectationSet(
            plan, quantities, (_comparison("gravity_dynamic", "gravity_static", "gravity_unused"),)
        )


@pytest.mark.parametrize(("side", "identifier"), [("left", "unknown"), ("right", "unknown")])
def test_set_rejects_unknown_quantity_on_each_side(side, identifier) -> None:
    plan, quantities = _context()
    kwargs = {side: identifier}
    with pytest.raises(ValueError, match="inconnue"):
        QuantityComparisonExpectationSet(plan, quantities, (_comparison(**kwargs),))


@pytest.mark.parametrize("side", ["left", "right"])
def test_set_rejects_non_quantity_on_each_side(side) -> None:
    plan, quantities = _context()
    kwargs = {side: "period_plot"}
    with pytest.raises(ValueError, match="QUANTITY"):
        QuantityComparisonExpectationSet(plan, quantities, (_comparison(**kwargs),))


def test_set_rejects_quantity_missing_from_quantity_expectations() -> None:
    plan, quantities = _context()
    partial = QuantityExpectationSet(plan, quantities.quantities[:1])
    with pytest.raises(ValueError, match="absente"):
        QuantityComparisonExpectationSet(plan, partial, (_comparison(),))


@pytest.mark.parametrize("missing", ["gravity_dynamic", "gravity_static"])
def test_set_requires_both_direct_dependencies(missing) -> None:
    left = _production("gravity_dynamic", ScientificProductionKind.QUANTITY)
    right = _production("gravity_static", ScientificProductionKind.QUANTITY)
    dependencies = tuple(identifier for identifier in (left.id, right.id) if identifier != missing)
    comparison = _production("gravity_comparison", ScientificProductionKind.COMPARISON, depends_on=dependencies)
    plan = ScientificProductionPlan("p", "Plan", (left, right, comparison))
    quantities = QuantityExpectationSet(plan, (
        ExpectedQuantity(left.id, "g", canonical_unit="m"),
        ExpectedQuantity(right.id, "g", canonical_unit="m"),
    ))
    with pytest.raises(ValueError, match="dépendre"):
        QuantityComparisonExpectationSet(plan, quantities, (_comparison(),))


def test_additional_dependencies_are_allowed() -> None:
    plan, quantities = _context(extra_dependency=True)
    expectation_set = QuantityComparisonExpectationSet(plan, quantities, (_comparison(),))
    assert expectation_set.get("gravity_comparison") is not None


def test_same_pair_reverse_pair_and_quantity_reuse_are_allowed() -> None:
    plan, quantities = _context(second_comparison=True)
    first = _comparison()
    reverse = _comparison(
        "gravity_comparison_reverse", "gravity_static", "gravity_dynamic",
        context=ComparisonPedagogicalContext.METHOD_LIMITATION_EXPECTED,
    )
    expectation_set = QuantityComparisonExpectationSet(plan, quantities, (first, reverse))
    assert expectation_set.for_quantity("gravity_dynamic") == (first, reverse)
    assert expectation_set.for_quantity("gravity_static") == (first, reverse)


def test_for_quantity_policies_are_explicit() -> None:
    expectation_set = _set(_comparison())
    assert expectation_set.for_quantity("gravity_unused") == ()
    assert expectation_set.for_quantity("period_plot") == ()
    assert expectation_set.for_quantity("gravity_comparison") == ()
    with pytest.raises(ValueError, match="inconnue"):
        expectation_set.for_quantity("unknown")


@pytest.mark.parametrize("context", list(ComparisonPedagogicalContext))
def test_for_context_supports_every_declared_context(context) -> None:
    comparison = _comparison(context=context)
    expectation_set = _set(comparison)
    assert expectation_set.for_context(context) == (comparison,)
    assert all(
        expectation_set.for_context(other) == ()
        for other in ComparisonPedagogicalContext
        if other is not context
    )
    with pytest.raises(TypeError):
        expectation_set.for_context(context.value)  # type: ignore[arg-type]


def test_in_evaluation_order_follows_plan_not_declaration_order() -> None:
    plan, quantities = _context(second_comparison=True)
    first = _comparison()
    reverse = _comparison("gravity_comparison_reverse", "gravity_static", "gravity_dynamic")
    expectation_set = QuantityComparisonExpectationSet(plan, quantities, (reverse, first))
    assert expectation_set.in_evaluation_order == (first, reverse)


def test_contract_stores_only_declarative_fields() -> None:
    names = {
        field.name
        for model in (
            NormalizedErrorThresholds,
            ExpectedQuantityComparison,
            QuantityComparisonExpectationSet,
        )
        for field in fields(model)
    }
    assert not names & {
        "value", "uncertainty", "normalized_error", "classification",
        "student_text", "binding_id", "cell_index", "notebook_path",
        "diagnostic", "feedback", "severity", "weight", "score", "penalty",
    }
