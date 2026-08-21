from decimal import Decimal

import pytest

from tpstudio.expectations import (
    EvaluationBasis,
    ExpectedDerivedQuantity,
    OperandRef,
    ProductionValue,
    RegressionParameter,
    RegressionParameterKind,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
    TeacherConstant,
    validate_derived_quantity_expectation,
)


def _plan(*items):
    return ScientificProductionPlan("synthetic", "Synthetic", tuple(items))


def _production(identifier, kind):
    return ScientificProductionSpec(
        identifier, identifier, kind, (EvaluationBasis.SUBMISSION_DERIVED,)
    )


def _expectation(target="p3", sources=()):
    sources = tuple(sources)
    return ExpectedDerivedQuantity(
        target,
        "q",
        sources,
        # Every declared source must occur in the rule.
        _chain(sources),
    )


def _chain(sources):
    expression = OperandRef(sources[0])
    for source in sources[1:]:
        from tpstudio.expectations import Add

        expression = Add(expression, OperandRef(source))
    return expression


def test_validates_opaque_quantity_and_plot_sources():
    plan = _plan(
        _production("p1", ScientificProductionKind.QUANTITY),
        _production("p2", ScientificProductionKind.PLOT),
        _production("p3", ScientificProductionKind.QUANTITY),
    )
    result = validate_derived_quantity_expectation(
        _expectation(
            sources=(
                ProductionValue("p1"),
                RegressionParameter("p2", RegressionParameterKind.SLOPE),
                TeacherConstant("k", Decimal("4")),
            )
        ),
        plan,
    )
    assert result.valid
    assert result.diagnostics == ()


def test_rejects_missing_source_and_target():
    plan = _plan(_production("p1", ScientificProductionKind.QUANTITY))
    result = validate_derived_quantity_expectation(
        _expectation(
            target="missing-target",
            sources=(ProductionValue("missing-source"),),
        ),
        plan,
    )
    assert not result.valid
    assert any("missing-target" in message for message in result.diagnostics)
    assert any("missing-source" in message for message in result.diagnostics)


@pytest.mark.parametrize(
    ("source", "kind", "expected"),
    [
        (ProductionValue("p2"), ScientificProductionKind.PLOT, "quantity"),
        (
            RegressionParameter("p1", RegressionParameterKind.INTERCEPT),
            ScientificProductionKind.QUANTITY,
            "plot",
        ),
        (
            RegressionParameter("p4", RegressionParameterKind.SLOPE),
            ScientificProductionKind.COMPARISON,
            "plot",
        ),
    ],
)
def test_rejects_incompatible_source_kind(source, kind, expected):
    plan = _plan(
        _production("p1", ScientificProductionKind.QUANTITY),
        _production("p2", ScientificProductionKind.PLOT),
        _production("p3", ScientificProductionKind.QUANTITY),
        _production("p4", ScientificProductionKind.COMPARISON),
    )
    result = validate_derived_quantity_expectation(
        _expectation(sources=(source,)), plan
    )
    assert not result.valid
    assert expected in result.diagnostics[0]


def test_rejects_non_quantity_target():
    plan = _plan(
        _production("interpretation", ScientificProductionKind.INTERPRETATION),
        _production("p1", ScientificProductionKind.QUANTITY),
    )
    result = validate_derived_quantity_expectation(
        _expectation(target="interpretation", sources=(ProductionValue("p1"),)),
        plan,
    )
    assert not result.valid
    assert "interpretation" in result.diagnostics[0]
    assert "quantity" in result.diagnostics[0]


def test_jb_shape_is_valid_but_wrong_regression_source_is_rejected():
    plan = _plan(
        _production("dynamic_graph", ScientificProductionKind.PLOT),
        _production("dynamic_torsion_constant", ScientificProductionKind.QUANTITY),
        _production("bar_inertia", ScientificProductionKind.QUANTITY),
    )
    valid = validate_derived_quantity_expectation(
        _expectation(
            target="bar_inertia",
            sources=(
                RegressionParameter("dynamic_graph", RegressionParameterKind.INTERCEPT),
                ProductionValue("dynamic_torsion_constant"),
                TeacherConstant("four_pi_squared", Decimal("39.478")),
            ),
        ),
        plan,
    )
    invalid = validate_derived_quantity_expectation(
        _expectation(
            target="bar_inertia",
            sources=(
                RegressionParameter("dynamic_torsion_constant", RegressionParameterKind.INTERCEPT),
                ProductionValue("dynamic_torsion_constant"),
                TeacherConstant("four_pi_squared", Decimal("39.478")),
            ),
        ),
        plan,
    )
    assert valid.valid
    assert not invalid.valid
    assert "plot" in " ".join(invalid.diagnostics)


def test_validation_does_not_require_plan_dependencies_to_match_sources():
    plan = ScientificProductionPlan(
        "synthetic", "Synthetic",
        (
            ScientificProductionSpec(
                "p1", "p1", ScientificProductionKind.QUANTITY,
                (EvaluationBasis.SUBMISSION_DERIVED,),
            ),
            ScientificProductionSpec(
                "p2", "p2", ScientificProductionKind.PLOT,
                (EvaluationBasis.SUBMISSION_DERIVED,),
            ),
            ScientificProductionSpec(
                "p3", "p3", ScientificProductionKind.QUANTITY,
                (EvaluationBasis.SUBMISSION_DERIVED,), depends_on=("p1",),
            ),
        ),
    )
    result = validate_derived_quantity_expectation(
        _expectation(
            sources=(
                ProductionValue("p1"),
                RegressionParameter("p2", RegressionParameterKind.SLOPE),
            )
        ), plan
    )
    assert result.valid
