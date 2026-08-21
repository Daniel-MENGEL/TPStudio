from decimal import Decimal

import numpy as np

from tpstudio.expectations import (
    Divide,
    DerivedSourceResolutionContext,
    DerivedSourceResolutionStatus,
    ExpectedDerivedQuantity,
    OperandRef,
    ProductionValue,
    RegressionParameter,
    RegressionParameterKind,
    TeacherConstant,
    evaluate_derived_quantity_from_analysis,
    resolve_derived_quantity_sources,
)
from tpstudio.graph_analysis import GraphAnalysis, GraphAnalysisTechnicalStatus
from tpstudio.regression import RegressionMethod
from tpstudio.regression_matching import RegressionSeriesMatchStatus
from tpstudio.regression_model import RegressionModelAnalysis, RegressionModelTechnicalStatus


def _expectation(target, sources, rule):
    return ExpectedDerivedQuantity(target, target, tuple(sources), rule)


def _graph(slope=2.5, intercept=1.2, status=GraphAnalysisTechnicalStatus.EVALUABLE):
    return GraphAnalysis(
        "graph-series", None, 0, 4, "AFFINE", slope, intercept,
        0.0, 0.0, 0.0, "none", "none", 1.0, 4, None, None, 0.0,
        0.0, "unavailable", "none", status, None, (), False,
    )


def test_production_value_uses_an_opaque_id_and_pipeline_evaluates_a_over_b():
    a, b = ProductionValue("production-17"), ProductionValue("production-18")
    expectation = _expectation("q", (a, b), Divide(OperandRef(a), OperandRef(b)))
    result = evaluate_derived_quantity_from_analysis(
        expectation,
        DerivedSourceResolutionContext({"production-17": 12, "production-18": 3}),
    )
    assert result.resolution.resolved
    assert result.evaluation is not None
    assert result.evaluation.value == Decimal("4")


def test_missing_and_non_scalar_production_values_are_diagnosed():
    source = ProductionValue("missing")
    expectation = _expectation("q", (source,), OperandRef(source))
    missing = resolve_derived_quantity_sources(expectation, DerivedSourceResolutionContext({}))
    assert missing.status is DerivedSourceResolutionStatus.MISSING_PRODUCTION
    assert missing.resolved_values == {}

    non_scalar = resolve_derived_quantity_sources(
        expectation,
        DerivedSourceResolutionContext({"missing": [1, 2]}),
    )
    assert non_scalar.status is DerivedSourceResolutionStatus.NON_SCALAR


def test_regression_adapter_resolves_slope_and_intercept_from_graph_analysis():
    slope = RegressionParameter("graph-1", RegressionParameterKind.SLOPE)
    intercept = RegressionParameter("graph-1", RegressionParameterKind.INTERCEPT)
    expectation = _expectation("q", (slope, intercept), Divide(OperandRef(intercept), OperandRef(slope)))
    context = DerivedSourceResolutionContext({}, graph_analyses={"graph-1": _graph()})
    result = evaluate_derived_quantity_from_analysis(expectation, context)
    assert result.evaluation is not None
    assert result.evaluation.value == Decimal("0.48")


def test_matching_graph_and_model_parameters_are_resolved_once():
    for parameter, expected in (
        (RegressionParameterKind.SLOPE, Decimal("2.5")),
        (RegressionParameterKind.INTERCEPT, Decimal("1.2")),
    ):
        source = RegressionParameter("graph-1", parameter)
        expectation = _expectation("q", (source,), OperandRef(source))
        model = RegressionModelAnalysis(
            "graph-1", "series-1", RegressionMethod.NUMPY_POLYFIT, 1,
            RegressionSeriesMatchStatus.EXACT, (2.5, 1.2), None, None, None,
            None, None, RegressionModelTechnicalStatus.EVALUABLE, (), False,
        )
        result = resolve_derived_quantity_sources(
            expectation,
            DerivedSourceResolutionContext(
                {},
                graph_analyses={"graph-1": _graph()},
                regression_model_analyses={"graph-1": model},
            ),
        )
        assert result.status is DerivedSourceResolutionStatus.RESOLVED
        assert result.resolved_values[source] == expected


def test_divergent_graph_and_model_parameters_return_a_conflict_for_both_kinds():
    for parameter in (RegressionParameterKind.SLOPE, RegressionParameterKind.INTERCEPT):
        source = RegressionParameter("graph-1", parameter)
        expectation = _expectation("q", (source,), OperandRef(source))
        model = RegressionModelAnalysis(
            "graph-1", "series-1", RegressionMethod.NUMPY_POLYFIT, 1,
            RegressionSeriesMatchStatus.EXACT, (3.0, 1.5), None, None, None,
            None, None, RegressionModelTechnicalStatus.EVALUABLE, (), False,
        )
        result = resolve_derived_quantity_sources(
            expectation,
            DerivedSourceResolutionContext(
                {}, graph_analyses={"graph-1": _graph()},
                regression_model_analyses={"graph-1": model},
            ),
        )
        assert result.status is DerivedSourceResolutionStatus.CONFLICTING_ANALYSES
        assert result.resolved_values == {}
        assert "valeurs concurrentes" in result.diagnostics[0]


def test_representation_difference_is_not_a_conflict():
    source = RegressionParameter("graph-1", RegressionParameterKind.INTERCEPT)
    expectation = _expectation("q", (source,), OperandRef(source))
    model = RegressionModelAnalysis(
        "graph-1", "series-1", RegressionMethod.NUMPY_POLYFIT, 1,
        RegressionSeriesMatchStatus.EXACT, (2.5, Decimal("1.2")), None, None, None,
        None, None, RegressionModelTechnicalStatus.EVALUABLE, (), False,
    )
    result = resolve_derived_quantity_sources(
        expectation,
        DerivedSourceResolutionContext({}, graph_analyses={"graph-1": _graph(intercept=1.2)}, regression_model_analyses={"graph-1": model}),
    )
    assert result.status is DerivedSourceResolutionStatus.RESOLVED


def test_invalid_or_missing_parameter_analysis_falls_back_to_valid_analysis():
    source = RegressionParameter("graph-1", RegressionParameterKind.INTERCEPT)
    expectation = _expectation("q", (source,), OperandRef(source))
    invalid_model = RegressionModelAnalysis(
        "graph-1", "series-1", RegressionMethod.NUMPY_POLYFIT, 1,
        RegressionSeriesMatchStatus.EXACT, None, None, None, None,
        None, None, RegressionModelTechnicalStatus.NOT_EVALUABLE, (), True,
    )
    result = resolve_derived_quantity_sources(
        expectation,
        DerivedSourceResolutionContext({}, graph_analyses={"graph-1": _graph()}, regression_model_analyses={"graph-1": invalid_model}),
    )
    assert result.status is DerivedSourceResolutionStatus.RESOLVED
    assert result.resolved_values[source] == Decimal("1.2")

    missing_model = RegressionModelAnalysis(
        "graph-1", "series-1", RegressionMethod.NUMPY_POLYFIT, 1,
        RegressionSeriesMatchStatus.EXACT, (2.5,), None, None, None,
        None, None, RegressionModelTechnicalStatus.EVALUABLE, (), False,
    )
    result = resolve_derived_quantity_sources(
        expectation,
        DerivedSourceResolutionContext({}, graph_analyses={"graph-1": _graph()}, regression_model_analyses={"graph-1": missing_model}),
    )
    assert result.status is DerivedSourceResolutionStatus.RESOLVED
    assert result.resolved_values[source] == Decimal("1.2")


def test_regression_absent_or_non_evaluable_is_controlled():
    source = RegressionParameter("graph-1", RegressionParameterKind.INTERCEPT)
    expectation = _expectation("q", (source,), OperandRef(source))
    absent = resolve_derived_quantity_sources(expectation, DerivedSourceResolutionContext({}))
    assert absent.status is DerivedSourceResolutionStatus.MISSING_ANALYSIS

    invalid = resolve_derived_quantity_sources(
        expectation,
        DerivedSourceResolutionContext({}, graph_analyses={"graph-1": _graph(status=GraphAnalysisTechnicalStatus.NOT_EVALUABLE)}),
    )
    assert invalid.status is DerivedSourceResolutionStatus.MISSING_REGRESSION


def test_regression_model_analysis_coefficients_are_supported():
    source = RegressionParameter("model-1", RegressionParameterKind.INTERCEPT)
    expectation = _expectation("q", (source,), OperandRef(source))
    model = RegressionModelAnalysis(
        "model-1", "series-1", RegressionMethod.NUMPY_POLYFIT, 1,
        RegressionSeriesMatchStatus.EXACT, (2.5, 1.2), None, None, None,
        None, None, RegressionModelTechnicalStatus.EVALUABLE, (), False,
    )
    result = resolve_derived_quantity_sources(
        expectation,
        DerivedSourceResolutionContext({}, regression_model_analyses={"model-1": model}),
    )
    assert result.resolved_values[source] == Decimal("1.2")


def test_polynomial_regression_never_exposes_slope_or_intercept():
    model = RegressionModelAnalysis(
        "model-2", "series-2", RegressionMethod.NUMPY_POLYFIT, 2,
        RegressionSeriesMatchStatus.EXACT, (3.0, 2.0, 1.0), None, None, None,
        None, None, RegressionModelTechnicalStatus.EVALUABLE, (), False,
    )
    for parameter in (RegressionParameterKind.SLOPE, RegressionParameterKind.INTERCEPT):
        source = RegressionParameter("model-2", parameter)
        expectation = _expectation("q", (source,), OperandRef(source))
        result = resolve_derived_quantity_sources(
            expectation,
            DerivedSourceResolutionContext({}, regression_model_analyses={"model-2": model}),
        )
        assert result.status is DerivedSourceResolutionStatus.UNSUPPORTED_REGRESSION_MODEL
        assert result.resolved_values == {}


def test_non_affine_model_falls_back_to_affine_graph_analysis():
    source = RegressionParameter("graph-1", RegressionParameterKind.INTERCEPT)
    expectation = _expectation("q", (source,), OperandRef(source))
    model = RegressionModelAnalysis(
        "graph-1", "series-1", RegressionMethod.NUMPY_POLYFIT, 2,
        RegressionSeriesMatchStatus.EXACT, (3.0, 2.0, 1.0), None, None, None,
        None, None, RegressionModelTechnicalStatus.EVALUABLE, (), False,
    )
    result = resolve_derived_quantity_sources(
        expectation,
        DerivedSourceResolutionContext(
            {}, graph_analyses={"graph-1": _graph(intercept=1.2)},
            regression_model_analyses={"graph-1": model},
        ),
    )
    assert result.status is DerivedSourceResolutionStatus.RESOLVED
    assert result.resolved_values[source] == Decimal("1.2")


def test_teacher_constant_resolves_without_copy_context():
    constant = TeacherConstant("k", 4)
    expectation = _expectation("q", (constant,), OperandRef(constant))
    result = resolve_derived_quantity_sources(expectation, DerivedSourceResolutionContext({}))
    assert result.status is DerivedSourceResolutionStatus.RESOLVED
    assert result.resolved_values[constant] == Decimal("4")


def test_numpy_scalar_is_normalized_but_bool_is_not_numeric():
    source = ProductionValue("q")
    expectation = _expectation("r", (source,), OperandRef(source))
    resolved = resolve_derived_quantity_sources(
        expectation, DerivedSourceResolutionContext({"q": np.float64(2.5)})
    )
    assert resolved.resolved_values[source] == Decimal("2.5")
    rejected = resolve_derived_quantity_sources(
        expectation, DerivedSourceResolutionContext({"q": True})
    )
    assert rejected.status is DerivedSourceResolutionStatus.NON_NUMERIC


def test_regression_pipeline_uses_quantity_and_teacher_constant_sources():
    intercept = RegressionParameter("graph-1", RegressionParameterKind.INTERCEPT)
    quantity = ProductionValue("quantity-1")
    constant = TeacherConstant("k", 4)
    # A structurally honest three-source rule: intercept * quantity / k.
    from tpstudio.expectations import Multiply
    expectation = _expectation(
        "q", (intercept, quantity, constant),
        Divide(Multiply(OperandRef(intercept), OperandRef(quantity)), OperandRef(constant)),
    )
    result = evaluate_derived_quantity_from_analysis(
        expectation,
        DerivedSourceResolutionContext({"quantity-1": 8}, graph_analyses={"graph-1": _graph(intercept=2.0)}),
    )
    assert result.evaluation is not None
    assert result.evaluation.value == Decimal("4")


def test_jb_pipeline_resolves_graph_intercept_and_dynamic_c_without_pre_resolved_mapping():
    intercept = RegressionParameter("dynamic_graph", RegressionParameterKind.INTERCEPT)
    dynamic_c = ProductionValue("dynamic_torsion_constant")
    constant = TeacherConstant("four_pi_squared", Decimal("39.47841760435743"))
    from tpstudio.expectations import Multiply
    expectation = ExpectedDerivedQuantity(
        "bar_inertia", "J_b", (intercept, dynamic_c, constant),
        Divide(Multiply(OperandRef(intercept), OperandRef(dynamic_c)), OperandRef(constant)),
    )
    result = evaluate_derived_quantity_from_analysis(
        expectation,
        DerivedSourceResolutionContext(
            {"dynamic_torsion_constant": Decimal("39.47841760435743")},
            graph_analyses={"dynamic_graph": _graph(intercept=2.0)},
        ),
    )
    assert result.resolution.resolved
    assert result.evaluation is not None
    assert result.evaluation.value == Decimal("2")
