from dataclasses import FrozenInstanceError
from decimal import Decimal, Inexact, ROUND_DOWN, getcontext, localcontext

import nbformat
import pytest

from tpstudio.assessment import (
    NotebookQuantityAssessmentItem,
    NotebookQuantityAssessmentSet,
    assess_notebook_quantities,
)
from tpstudio.evaluation import (
    QuantityComparisonEvaluation,
    QuantityComparisonEvaluationSet,
    QuantityComparisonEvaluationStatus as Status,
    QuantityComparisonEvaluator,
    QuantityComparisonNotEvaluableReason as Reason,
    evaluate_quantity_comparisons,
)
from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    ComparisonPedagogicalContext,
    EvaluationBasis,
    ExpectedQuantity,
    ExpectedQuantityComparison,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
    NormalizedErrorThresholds,
    PresenceRequirement,
    QuantityComparisonExpectationSet,
    QuantityExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
)


def _case(
    left="x1 = (9.7 ± 0.4) m",
    right="x2 = (9.8 ± 0.2) m",
    *,
    left_bindings=1,
    right_bindings=1,
    missing_left=0,
    missing_right=0,
    right_units=("m",),
    thresholds=None,
    context=ComparisonPedagogicalContext.OPEN,
):
    left_spec = ScientificProductionSpec("left", "Left", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    right_spec = ScientificProductionSpec("right", "Right", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    comparison_spec = ScientificProductionSpec("comparison", "Comparison", ScientificProductionKind.COMPARISON, (EvaluationBasis.CROSS_PRODUCTION,), depends_on=("left", "right"))
    plan = ScientificProductionPlan("plan", "Plan", (left_spec, right_spec, comparison_spec))
    quantities = QuantityExpectationSet(plan, (
        ExpectedQuantity("left", "x1", canonical_unit="m", uncertainty_requirement=PresenceRequirement.REQUIRED),
        ExpectedQuantity("right", "x2", canonical_unit="m", accepted_units=tuple(unit for unit in right_units if unit != "m"), uncertainty_requirement=PresenceRequirement.REQUIRED),
    ))
    cells = []
    bindings = []
    for side, source, count, missing in (("left", left, left_bindings, missing_left), ("right", right, right_bindings, missing_right)):
        for index in range(count):
            cell_id = f"{side}-{index}"
            cells.append(nbformat.v4.new_markdown_cell(source, id=cell_id))
            bindings.append(CellProductionBinding(f"binding-{side}-{index}", side, NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, cell_id), CellTextScope.full_source()))
        for index in range(missing):
            bindings.append(CellProductionBinding(f"missing-{side}-{index}", side, NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, f"absent-{side}-{index}"), CellTextScope.full_source()))
    binding_plan = NotebookBindingPlan("bindings", "Bindings", plan, tuple(bindings))
    notebook = nbformat.v4.new_notebook(cells=cells)
    assessments = assess_notebook_quantities(notebook, binding_plan, quantities)
    expectation = ExpectedQuantityComparison(
        "comparison", "left", "right",
        thresholds=thresholds or NormalizedErrorThresholds(),
        pedagogical_context=context,
        context_note="note",
    )
    expectations = QuantityComparisonExpectationSet(plan, quantities, (expectation,))
    return assessments, expectations


def _evaluate(*args, **kwargs):
    assessments, expectations = _case(*args, **kwargs)
    return evaluate_quantity_comparisons(assessments, expectations), assessments, expectations


def test_enum_values_are_exact() -> None:
    assert tuple(item.value for item in Status) == ("coherent", "moderately_incoherent", "strongly_incoherent", "not_evaluable")
    assert tuple(item.value for item in Reason) == (
        "left_assessment_unavailable", "right_assessment_unavailable",
        "left_assessment_ambiguous", "right_assessment_ambiguous",
        "left_observation_missing", "right_observation_missing",
        "left_value_invalid", "right_value_invalid",
        "left_uncertainty_missing", "right_uncertainty_missing",
        "left_uncertainty_not_strictly_positive", "right_uncertainty_not_strictly_positive",
        "left_unit_missing", "right_unit_missing", "unit_mismatch",
    )


def test_coherent_decimal_calculation_properties_and_identity() -> None:
    result, assessments, expectations = _evaluate()
    evaluation = result.get("comparison")
    assert evaluation is not None
    assert evaluation.status is Status.COHERENT
    assert abs(evaluation.normalized_error - Decimal("0.2236067977499789696409173669")) < Decimal("1e-27")
    assert evaluation.expectation is expectations.get("comparison")
    assert evaluation.left_item is assessments.for_production("left")[0]
    assert evaluation.right_item is assessments.for_production("right")[0]
    assert evaluation.evaluable and evaluation.coherent
    assert not evaluation.not_evaluable
    assert evaluation.left_value == Decimal("9.7")
    assert evaluation.right_value == Decimal("9.8")
    assert evaluation.left_uncertainty == Decimal("0.4")
    assert evaluation.right_uncertainty == Decimal("0.2")
    assert evaluation.unit == "m"
    assert evaluation.thresholds == NormalizedErrorThresholds()
    assert evaluation.context_note == "note"


@pytest.mark.parametrize(
    ("right", "expected"),
    [
        ("x2 = (10.8 ± 0.2) m", Status.MODERATELY_INCOHERENT),
        ("x2 = (12.0 ± 0.2) m", Status.STRONGLY_INCOHERENT),
        ("x2 = (10.7 ± 0.4) m", Status.MODERATELY_INCOHERENT),
        ("x2 = (11.7 ± 0.4) m", Status.STRONGLY_INCOHERENT),
    ],
)
def test_objective_classification_including_exact_boundaries(right, expected) -> None:
    result, _, _ = _evaluate(left="x1 = (9.7 ± 0.3) m", right=right)
    assert result.evaluations[0].status is expected


def test_custom_thresholds_and_pedagogical_context_do_not_change_objective_result() -> None:
    result, _, _ = _evaluate(
        right="x2 = (12.0 ± 0.2) m",
        thresholds=NormalizedErrorThresholds(Decimal("1"), Decimal("3")),
        context=ComparisonPedagogicalContext.METHOD_LIMITATION_EXPECTED,
    )
    item = result.evaluations[0]
    assert item.strongly_incoherent
    assert item.pedagogical_context is ComparisonPedagogicalContext.METHOD_LIMITATION_EXPECTED


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"left_bindings": 0, "missing_left": 1}, Reason.LEFT_ASSESSMENT_UNAVAILABLE),
        ({"right_bindings": 0, "missing_right": 1}, Reason.RIGHT_ASSESSMENT_UNAVAILABLE),
        ({"left_bindings": 2}, Reason.LEFT_ASSESSMENT_AMBIGUOUS),
        ({"right_bindings": 2}, Reason.RIGHT_ASSESSMENT_AMBIGUOUS),
        ({"left": "Pas de résultat"}, Reason.LEFT_OBSERVATION_MISSING),
        ({"right": "Pas de résultat"}, Reason.RIGHT_OBSERVATION_MISSING),
        ({"left": "x1 = 9.7 m"}, Reason.LEFT_UNCERTAINTY_MISSING),
        ({"right": "x2 = 9.8 m"}, Reason.RIGHT_UNCERTAINTY_MISSING),
        ({"left": "x1 = (9.7 ± 0) m"}, Reason.LEFT_UNCERTAINTY_NOT_STRICTLY_POSITIVE),
        ({"right": "x2 = (9.8 ± -0.2) m"}, Reason.RIGHT_UNCERTAINTY_NOT_STRICTLY_POSITIVE),
        ({"left": "x1 = (9.7 ± 0.4)"}, Reason.LEFT_UNIT_MISSING),
        ({"right": "x2 = (9.8 ± 0.2)"}, Reason.RIGHT_UNIT_MISSING),
        ({"right": "x2 = (9.8 ± 0.2) cm", "right_units": ("m", "cm")}, Reason.UNIT_MISMATCH),
    ],
)
def test_not_evaluable_reasons(kwargs, reason) -> None:
    result, _, _ = _evaluate(**kwargs)
    evaluation = result.evaluations[0]
    assert evaluation.status is Status.NOT_EVALUABLE
    assert reason in evaluation.not_evaluable_reasons
    assert evaluation.normalized_error is None
    assert evaluation.not_evaluable and evaluation.unit is None


def test_one_assessed_remains_usable_with_failed_binding() -> None:
    result, _, _ = _evaluate(missing_left=1)
    assert result.evaluations[0].status is Status.COHERENT
    assert len(result.evaluations[0].left_candidates) == 2


def test_multiple_reasons_have_deterministic_order() -> None:
    result, _, _ = _evaluate(left="x1 = 9.7", right="x2 = 9.8")
    assert result.evaluations[0].not_evaluable_reasons == (
        Reason.LEFT_UNCERTAINTY_MISSING,
        Reason.RIGHT_UNCERTAINTY_MISSING,
        Reason.LEFT_UNIT_MISSING,
        Reason.RIGHT_UNIT_MISSING,
    )


@pytest.mark.parametrize(
    ("side", "reason"),
    [("left", Reason.LEFT_VALUE_INVALID), ("right", Reason.RIGHT_VALUE_INVALID)],
)
def test_invalid_observed_value_is_not_evaluable(side, reason) -> None:
    assessments, expectations = _case()
    item = assessments.for_production(side)[0]
    assert item.assessment is not None
    observation = item.assessment.selected_observation
    assert observation is not None
    object.__setattr__(observation, "value", Decimal("NaN"))
    evaluation = evaluate_quantity_comparisons(assessments, expectations).evaluations[0]
    assert evaluation.status is Status.NOT_EVALUABLE
    assert reason in evaluation.not_evaluable_reasons


def test_global_decimal_context_is_unchanged_and_calls_are_deterministic() -> None:
    assessments, expectations = _case()
    before = getcontext().copy()
    first = QuantityComparisonEvaluator().evaluate(assessments, expectations)
    second = QuantityComparisonEvaluator().evaluate(assessments, expectations)
    assert first == second
    after = getcontext()
    assert (after.prec, after.rounding, after.Emin, after.Emax, after.capitals,
            after.clamp, after.traps.copy(), after.flags.copy()) == (
        before.prec, before.rounding, before.Emin, before.Emax, before.capitals,
        before.clamp, before.traps.copy(), before.flags.copy()
    )


def test_calculation_is_independent_from_hostile_caller_context() -> None:
    assessments, expectations = _case()
    reference = evaluate_quantity_comparisons(assessments, expectations)
    with localcontext() as hostile:
        hostile.prec = 3
        hostile.rounding = ROUND_DOWN
        hostile.Emin = -10
        hostile.Emax = 10
        hostile.traps[Inexact] = True
        hostile.clear_flags()
        before = hostile.copy()
        actual = evaluate_quantity_comparisons(assessments, expectations)
        assert actual.evaluations[0].normalized_error == reference.evaluations[0].normalized_error
        assert actual.evaluations[0].status is reference.evaluations[0].status
        assert hostile.prec == before.prec
        assert hostile.rounding == before.rounding
        assert hostile.Emin == before.Emin and hostile.Emax == before.Emax
        assert hostile.traps == before.traps
        assert hostile.flags == before.flags


def test_set_collection_api() -> None:
    result, _, _ = _evaluate(right="x2 = (12.0 ± 0.2) m")
    item = result.evaluations[0]
    assert tuple(result) == (item,)
    assert len(result) == 1
    assert result.for_quantity("left") == (item,)
    assert result.for_status(Status.STRONGLY_INCOHERENT) == (item,)
    assert result.strongly_incoherent == (item,)
    assert result.coherent == result.moderately_incoherent == result.not_evaluable == ()
    assert result.all_evaluable and not result.has_not_evaluable
    assert result.has_incoherence and result.has_strong_incoherence
    with pytest.raises(ValueError):
        result.for_quantity("unknown")
    with pytest.raises(TypeError):
        result.for_status("coherent")


def test_models_are_immutable_and_convert_collections_to_tuples() -> None:
    result, assessments, expectations = _evaluate()
    item = result.evaluations[0]
    rebuilt = QuantityComparisonEvaluation(item.expectation, list(item.left_candidates), list(item.right_candidates), item.left_item, item.right_item, item.status, normalized_error=item.normalized_error)
    rebuilt_set = QuantityComparisonEvaluationSet(expectations, assessments, [rebuilt])
    assert isinstance(rebuilt.left_candidates, tuple)
    assert isinstance(rebuilt_set.evaluations, tuple)
    with pytest.raises(FrozenInstanceError):
        rebuilt.status = Status.NOT_EVALUABLE
    with pytest.raises(FrozenInstanceError):
        rebuilt_set.evaluations = ()


def test_invalid_result_invariants_are_rejected() -> None:
    result, _, _ = _evaluate()
    item = result.evaluations[0]
    with pytest.raises(ValueError):
        QuantityComparisonEvaluation(item.expectation, item.left_candidates, item.right_candidates, item.left_item, item.right_item, Status.NOT_EVALUABLE)
    with pytest.raises(ValueError):
        QuantityComparisonEvaluation(item.expectation, item.left_candidates, item.right_candidates, item.left_item, item.right_item, Status.COHERENT, (Reason.UNIT_MISMATCH,), item.normalized_error)
    with pytest.raises(TypeError):
        QuantityComparisonEvaluation(item.expectation, item.left_candidates, item.right_candidates, item.left_item, item.right_item, Status.NOT_EVALUABLE, ("bad",))
    with pytest.raises(ValueError):
        QuantityComparisonEvaluation(item.expectation, item.left_candidates, item.right_candidates, item.left_item, item.right_item, Status.NOT_EVALUABLE, (Reason.UNIT_MISMATCH, Reason.UNIT_MISMATCH))
    with pytest.raises(TypeError):
        QuantityComparisonEvaluation(item.expectation, item.left_candidates, item.right_candidates, item.left_item, item.right_item, Status.COHERENT, normalized_error=1)


def test_ambiguous_candidates_cannot_have_an_arbitrarily_selected_item() -> None:
    result, _, _ = _evaluate(left_bindings=2)
    item = result.evaluations[0]
    with pytest.raises(ValueError, match="unicité"):
        QuantityComparisonEvaluation(
            item.expectation, item.left_candidates, item.right_candidates,
            item.left_candidates[0], item.right_item, item.status,
            item.not_evaluable_reasons,
        )


def test_unavailable_candidates_cannot_have_a_selected_item() -> None:
    result, _, _ = _evaluate(left_bindings=0, missing_left=1)
    item = result.evaluations[0]
    with pytest.raises(ValueError, match="unicité"):
        QuantityComparisonEvaluation(
            item.expectation, item.left_candidates, item.right_candidates,
            item.left_candidates[0], item.right_item, item.status,
            item.not_evaluable_reasons,
        )


def test_unique_assessed_candidate_must_be_selected() -> None:
    result, _, _ = _evaluate()
    item = result.evaluations[0]
    with pytest.raises(ValueError, match="unicité"):
        QuantityComparisonEvaluation(
            item.expectation, item.left_candidates, item.right_candidates,
            None, item.right_item, item.status, normalized_error=item.normalized_error,
        )


@pytest.mark.parametrize(
    "false_reason",
    [Reason.LEFT_ASSESSMENT_UNAVAILABLE, Reason.UNIT_MISMATCH, Reason.LEFT_UNIT_MISSING],
)
def test_not_evaluable_reasons_must_exactly_match_observed_state(false_reason) -> None:
    result, _, _ = _evaluate()
    item = result.evaluations[0]
    with pytest.raises(ValueError, match="exactement"):
        QuantityComparisonEvaluation(
            item.expectation, item.left_candidates, item.right_candidates,
            item.left_item, item.right_item, Status.NOT_EVALUABLE, (false_reason,),
        )


def test_evaluation_set_rejects_candidates_from_another_assessment_set() -> None:
    result, assessments, expectations = _evaluate()
    foreign_items = tuple(
        NotebookQuantityAssessmentItem(
            item.resolution, item.production_spec, item.status, item.assessment
        )
        for item in assessments
    )
    foreign_set = NotebookQuantityAssessmentSet(
        assessments.resolution_set, foreign_items
    )
    foreign_evaluation = evaluate_quantity_comparisons(
        foreign_set, expectations
    ).evaluations[0]
    with pytest.raises(ValueError, match="étrangers"):
        QuantityComparisonEvaluationSet(
            expectations, assessments, (foreign_evaluation,)
        )


def test_incoherent_plan_and_quantity_expectation_set_are_rejected() -> None:
    assessments, _ = _case()[:2]
    _, foreign_expectations = _case()[:2]
    with pytest.raises(ValueError):
        evaluate_quantity_comparisons(assessments, foreign_expectations)
    with pytest.raises(TypeError):
        evaluate_quantity_comparisons(object(), foreign_expectations)


def test_public_api_has_no_diagnostic_feedback_or_scoring() -> None:
    result, _, _ = _evaluate()
    item = result.evaluations[0]
    for name in ("diagnostics", "feedback", "penalty", "score", "grade", "accepted"):
        assert not hasattr(item, name)
