from decimal import Decimal

import pytest

from tpstudio.expectations import (
    Constant,
    Divide,
    ExpectedDerivedQuantity,
    Multiply,
    OperandRef,
    ProductionValue,
    RegressionParameter,
    RegressionParameterKind,
    TeacherConstant,
    DerivedQuantityEvaluationStatus,
    assess_expectation_sufficiency,
    evaluate_derived_quantity,
    ExpectationSufficiency,
)


def derived(target, sources, rule, **kwargs):
    return ExpectedDerivedQuantity(target, target, tuple(sources), rule, **kwargs)


def test_divides_two_generic_production_values():
    a, b = ProductionValue("a"), ProductionValue("b")
    expectation = derived("q", (a, b), Divide(OperandRef(a), OperandRef(b)))
    result = evaluate_derived_quantity(expectation, {a: 12, b: 3})
    assert result.status is DerivedQuantityEvaluationStatus.CALCULATED
    assert result.value == Decimal("4")
    assert result.sources_used == (("production", "a"), ("production", "b"))


def test_multiplies_two_sources_and_supports_u_over_i():
    x, y = ProductionValue("x"), ProductionValue("y")
    expectation = derived("r", (x, y), Multiply(OperandRef(x), OperandRef(y)))
    assert evaluate_derived_quantity(expectation, {x: 2, y: 5}).value == Decimal("10")

    u, i = ProductionValue("U"), ProductionValue("I")
    resistance = derived("R", (u, i), Divide(OperandRef(u), OperandRef(i)))
    assert evaluate_derived_quantity(resistance, {u: 12, i: 3}).value == Decimal("4")


def test_teacher_constant_is_safe_and_serializable_in_the_tree():
    x = ProductionValue("x")
    k = TeacherConstant("four_pi_squared", Decimal("39.47841760435743"), "1")
    expectation = derived("q", (x, k), Divide(OperandRef(x), OperandRef(k)))
    result = evaluate_derived_quantity(expectation, {x: Decimal("39.47841760435743")})
    assert result.status is DerivedQuantityEvaluationStatus.CALCULATED
    assert result.value == Decimal("1")


def test_regression_parameters_are_generic_slope_and_intercept_operands():
    intercept = RegressionParameter("graph", RegressionParameterKind.INTERCEPT)
    slope = RegressionParameter("graph", RegressionParameterKind.SLOPE)
    expectation = derived("q", (intercept, slope), Multiply(OperandRef(intercept), OperandRef(slope)))
    result = evaluate_derived_quantity(expectation, {intercept: 4, slope: 2})
    assert result.value == Decimal("8")


def test_missing_and_non_numeric_sources_are_diagnosed_without_invention():
    a, b = ProductionValue("a"), ProductionValue("b")
    expectation = derived("q", (a, b), Divide(OperandRef(a), OperandRef(b)))
    missing = evaluate_derived_quantity(expectation, {a: 1})
    assert missing.status is DerivedQuantityEvaluationStatus.MISSING_SOURCE
    assert missing.value is None
    assert "source manquante" in missing.diagnostics[0]

    non_numeric = evaluate_derived_quantity(expectation, {a: 1, b: "trois"})
    assert non_numeric.status is DerivedQuantityEvaluationStatus.NON_NUMERIC_SOURCE
    assert non_numeric.value is None


def test_division_by_zero_is_controlled():
    a, b = ProductionValue("a"), ProductionValue("b")
    expectation = derived("q", (a, b), Divide(OperandRef(a), OperandRef(b)))
    result = evaluate_derived_quantity(expectation, {a: 1, b: 0})
    assert result.status is DerivedQuantityEvaluationStatus.DIVISION_BY_ZERO
    assert result.value is None


def test_self_reference_and_undeclared_sources_are_rejected():
    q = ProductionValue("q")
    with pytest.raises(ValueError, match="elle-même"):
        derived("q", (q,), OperandRef(q))

    a, b = ProductionValue("a"), ProductionValue("b")
    with pytest.raises(ValueError, match="source non déclarée"):
        derived("q", (a,), Divide(OperandRef(a), OperandRef(b)))


def test_jb_shape_is_generic_configuration_only():
    intercept = RegressionParameter("dynamic_graph", RegressionParameterKind.INTERCEPT)
    dynamic_c = ProductionValue("dynamic_torsion_constant")
    four_pi_squared = TeacherConstant("four_pi_squared", Decimal("39.47841760435743"))
    expectation = ExpectedDerivedQuantity(
        "bar_inertia",
        "J_b",
        (intercept, dynamic_c, four_pi_squared),
        Divide(Multiply(OperandRef(intercept), OperandRef(dynamic_c)), OperandRef(four_pi_squared)),
        canonical_unit="kg m^2",
    )
    result = evaluate_derived_quantity(
        expectation,
        {intercept: Decimal("2"), dynamic_c: Decimal("39.47841760435743")},
    )
    assert result.status is DerivedQuantityEvaluationStatus.CALCULATED
    assert result.value == Decimal("2")
    assert assess_expectation_sufficiency(expectation).sufficiency is ExpectationSufficiency.ANALYZABLE


def test_derived_quantity_is_not_the_normalized_error_engine():
    # E_n remains a comparison concern; this generic algebra has no comparison
    # or normalized-error special case.
    assert "normalized_error" not in evaluate_derived_quantity.__doc__
