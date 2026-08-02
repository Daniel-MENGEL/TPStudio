from dataclasses import FrozenInstanceError
from decimal import Decimal, Inexact, ROUND_DOWN, getcontext, localcontext

import nbformat
import pytest

from tpstudio.assessment import assess_notebook_quantities
from tpstudio.evaluation import (
    StudentNormalizedErrorEvaluation,
    StudentNormalizedErrorEvaluationSet,
    StudentNormalizedErrorEvaluationStatus as Status,
    StudentNormalizedErrorEvaluator,
    StudentNormalizedErrorNotEvaluableReason as Reason,
    evaluate_quantity_comparisons,
    evaluate_student_normalized_errors,
)
from tpstudio.reasoning import (
    StudentNormalizedErrorDetection,
    StudentNormalizedErrorObservation,
    extract_student_normalized_error,
)
from tpstudio.expectations import (
    CellProductionBinding, CellTextScope, EvaluationBasis, ExpectedQuantity,
    ExpectedQuantityComparison, ExpectedStudentNormalizedError,
    NotebookBindingPlan, NotebookCellSelector, NotebookCellSelectorKind,
    PresenceRequirement, QuantityComparisonExpectationSet,
    QuantityExpectationSet, ScientificProductionKind, ScientificProductionPlan,
    ScientificProductionSpec, StudentNormalizedErrorExpectationSet,
)


def _case(student_texts=("Calcul : E_n = 2,2.\nConclusion.",), *, missing_sources=0, left="x1 = (0 ± 0.4) m", tolerance=Decimal("0.1")):
    left_spec = ScientificProductionSpec("left", "Left", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    right_spec = ScientificProductionSpec("right", "Right", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    comparison = ScientificProductionSpec("comparison", "Comparison", ScientificProductionKind.COMPARISON, (EvaluationBasis.CROSS_PRODUCTION,), depends_on=("left", "right"))
    plan = ScientificProductionPlan("p", "Plan", (left_spec, right_spec, comparison))
    quantities = QuantityExpectationSet(plan, (
        ExpectedQuantity("left", "x1", canonical_unit="m", uncertainty_requirement=PresenceRequirement.REQUIRED),
        ExpectedQuantity("right", "x2", canonical_unit="m", uncertainty_requirement=PresenceRequirement.REQUIRED),
    ))
    cells = [nbformat.v4.new_markdown_cell(left, id="left"), nbformat.v4.new_markdown_cell("x2 = (1 ± 0.2) m", id="right")]
    bindings = [
        CellProductionBinding("b-left", "left", NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, "left"), CellTextScope.full_source()),
        CellProductionBinding("b-right", "right", NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, "right"), CellTextScope.full_source()),
    ]
    for index, text in enumerate(student_texts):
        identifier = f"comparison-{index}"
        cells.append(nbformat.v4.new_markdown_cell(text, id=identifier))
        bindings.append(CellProductionBinding(f"b-{identifier}", "comparison", NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, identifier), CellTextScope.full_source()))
    for index in range(missing_sources):
        bindings.append(CellProductionBinding(f"missing-{index}", "comparison", NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, f"absent-{index}"), CellTextScope.full_source()))
    binding_plan = NotebookBindingPlan("b", "Bindings", plan, tuple(bindings))
    notebook = nbformat.v4.new_notebook(cells=cells)
    assessments = assess_notebook_quantities(notebook, binding_plan, quantities)
    comparison_expectation = ExpectedQuantityComparison("comparison", "left", "right")
    comparison_set = QuantityComparisonExpectationSet(plan, quantities, (comparison_expectation,))
    references = evaluate_quantity_comparisons(assessments, comparison_set)
    expected = ExpectedStudentNormalizedError("comparison", ("E_n", "En", "Eₙ"), tolerance)
    expectation_set = StudentNormalizedErrorExpectationSet(comparison_set, (expected,))
    return references, expectation_set


def _evaluate(*args, **kwargs):
    references, expectations = _case(*args, **kwargs)
    return evaluate_student_normalized_errors(references, expectations), references, expectations


def test_enum_values_are_exact() -> None:
    assert tuple(item.value for item in Status) == ("matches_reference", "differs_from_reference", "not_evaluable")
    assert tuple(item.value for item in Reason) == ("source_unavailable", "source_ambiguous", "student_value_missing", "student_value_ambiguous", "student_value_negative", "reference_not_evaluable")


def test_rounded_student_value_matches_reference_and_properties() -> None:
    result, references, expectations = _evaluate()
    item = result.evaluations[0]
    assert item.status is Status.MATCHES_REFERENCE
    assert item.student_value == Decimal("2.2")
    assert item.reference_value == references.evaluations[0].normalized_error
    assert item.absolute_difference < Decimal("0.1")
    assert item.tolerance == Decimal("0.1")
    assert item.matches_reference and item.evaluable
    assert not item.differs_from_reference and not item.not_evaluable
    assert item.expectation is expectations.expectations[0]
    assert item.reference_evaluation is references.evaluations[0]
    assert item.source_text_start is not None and item.source_text_end is not None


@pytest.mark.parametrize(
    ("text", "tolerance", "expected"),
    [
        ("En = 2.1", Decimal("0.136067977499789696409173669"), Status.MATCHES_REFERENCE),
        ("En = 2.1", Decimal("0.13"), Status.DIFFERS_FROM_REFERENCE),
        ("En = 2.236067977499789696409173669", Decimal("0"), Status.MATCHES_REFERENCE),
        ("En = 2.2", Decimal("0"), Status.DIFFERS_FROM_REFERENCE),
    ],
)
def test_tolerance_boundary_and_zero_policy(text, tolerance, expected) -> None:
    result, _, _ = _evaluate((text,), tolerance=tolerance)
    assert result.evaluations[0].status is expected


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"student_texts": ("aucune valeur",)}, Reason.STUDENT_VALUE_MISSING),
        ({"student_texts": ("En=2 puis E_n=2.1",)}, Reason.STUDENT_VALUE_AMBIGUOUS),
        ({"student_texts": ("En=-2",)}, Reason.STUDENT_VALUE_NEGATIVE),
        ({"student_texts": (), "missing_sources": 1}, Reason.SOURCE_UNAVAILABLE),
        ({"student_texts": ("En=2", "En=2.1")}, Reason.SOURCE_AMBIGUOUS),
        ({"left": "x1 = 0 m"}, Reason.REFERENCE_NOT_EVALUABLE),
        ({"student_texts": ("En = abs(x1-x2)/sqrt(u1**2+u2**2)",)}, Reason.STUDENT_VALUE_MISSING),
    ],
)
def test_not_evaluable_cases(kwargs, reason) -> None:
    result, _, _ = _evaluate(**kwargs)
    item = result.evaluations[0]
    assert item.status is Status.NOT_EVALUABLE
    assert reason in item.not_evaluable_reasons
    assert item.absolute_difference is None


def test_pathological_student_literal_becomes_missing_without_exact_expansion() -> None:
    result, _, _ = _evaluate(("En = 1e999999999",))
    item = result.evaluations[0]
    assert item.status is Status.NOT_EVALUABLE
    assert item.not_evaluable_reasons == (Reason.STUDENT_VALUE_MISSING,)


def test_unique_resolved_source_survives_failed_binding() -> None:
    result, _, _ = _evaluate(missing_sources=1)
    item = result.evaluations[0]
    assert item.status is Status.MATCHES_REFERENCE
    assert len(item.source_candidates) == 2


def test_source_and_reference_reasons_are_combined_in_order() -> None:
    result, _, _ = _evaluate((), missing_sources=1, left="x1 = 0 m")
    assert result.evaluations[0].not_evaluable_reasons == (
        Reason.SOURCE_UNAVAILABLE, Reason.REFERENCE_NOT_EVALUABLE
    )


def test_exact_difference_is_independent_of_hostile_decimal_context() -> None:
    references, expectations = _case()
    reference = evaluate_student_normalized_errors(references, expectations)
    before_global = getcontext().copy()
    with localcontext() as hostile:
        hostile.prec = 2
        hostile.rounding = ROUND_DOWN
        hostile.traps[Inexact] = True
        before = hostile.copy()
        actual = evaluate_student_normalized_errors(references, expectations)
        assert actual.evaluations[0].absolute_difference == reference.evaluations[0].absolute_difference
        assert hostile.prec == before.prec and hostile.rounding == before.rounding
        assert hostile.traps == before.traps and hostile.flags == before.flags
    assert getcontext().prec == before_global.prec and getcontext().rounding == before_global.rounding


def test_model_invariants_reject_wrong_selection_reasons_and_difference() -> None:
    result, _, _ = _evaluate()
    item = result.evaluations[0]
    with pytest.raises(ValueError):
        StudentNormalizedErrorEvaluation(item.expectation, item.reference_evaluation, item.source_candidates, None, item.detection, item.student_observation, item.status, absolute_difference=item.absolute_difference)
    with pytest.raises(ValueError):
        StudentNormalizedErrorEvaluation(item.expectation, item.reference_evaluation, item.source_candidates, item.source_resolution, item.detection, None, item.status, absolute_difference=item.absolute_difference)
    with pytest.raises(ValueError):
        StudentNormalizedErrorEvaluation(item.expectation, item.reference_evaluation, item.source_candidates, item.source_resolution, item.detection, item.student_observation, Status.NOT_EVALUABLE, (Reason.STUDENT_VALUE_MISSING,))
    with pytest.raises(ValueError):
        StudentNormalizedErrorEvaluation(item.expectation, item.reference_evaluation, item.source_candidates, item.source_resolution, item.detection, item.student_observation, item.status, absolute_difference=Decimal("9"))


def test_manual_model_rejects_detection_from_another_text() -> None:
    result, _, _ = _evaluate(("En = 2,2",))
    item = result.evaluations[0]
    foreign = extract_student_normalized_error("En = 9,9", item.expectation)
    with pytest.raises(ValueError, match="texte résolu"):
        StudentNormalizedErrorEvaluation(
            item.expectation, item.reference_evaluation, item.source_candidates,
            item.source_resolution, foreign, foreign.selected_observation,
            Status.DIFFERS_FROM_REFERENCE,
            absolute_difference=Decimal("7.663932022500210303590826331"),
        )


def test_manual_model_rejects_detection_omitting_source_occurrences() -> None:
    result, _, _ = _evaluate(("En = 2,2 puis En = 2,3",))
    item = result.evaluations[0]
    assert item.detection is not None
    forged = StudentNormalizedErrorDetection(
        item.expectation, (item.detection.observations[0],)
    )
    with pytest.raises(ValueError, match="texte résolu"):
        StudentNormalizedErrorEvaluation(
            item.expectation, item.reference_evaluation, item.source_candidates,
            item.source_resolution, forged, forged.selected_observation,
            Status.MATCHES_REFERENCE, absolute_difference=Decimal("0.036067977499789696409173669"),
        )


def test_manual_model_rejects_empty_detection_for_nonempty_source() -> None:
    result, _, _ = _evaluate(("En = 2,2",))
    item = result.evaluations[0]
    empty = StudentNormalizedErrorDetection(item.expectation, ())
    with pytest.raises(ValueError, match="texte résolu"):
        StudentNormalizedErrorEvaluation(
            item.expectation, item.reference_evaluation, item.source_candidates,
            item.source_resolution, empty, None, Status.NOT_EVALUABLE,
            (Reason.STUDENT_VALUE_MISSING,),
        )


def test_manual_model_rejects_raw_value_and_offsets_not_matching_source() -> None:
    result, _, _ = _evaluate(("En = 2,3",))
    item = result.evaluations[0]
    forged_observation = StudentNormalizedErrorObservation(
        item.expectation, "En", "=", "9,9", Decimal("9.9"), 0, 8, 5, 8
    )
    forged = StudentNormalizedErrorDetection(item.expectation, (forged_observation,))
    with pytest.raises(ValueError, match="texte résolu"):
        StudentNormalizedErrorEvaluation(
            item.expectation, item.reference_evaluation, item.source_candidates,
            item.source_resolution, forged, forged_observation,
            Status.DIFFERS_FROM_REFERENCE, absolute_difference=Decimal("7.663932022500210303590826331"),
        )


@pytest.mark.parametrize(
    ("student_texts", "expected_calls"),
    [(("En=2,2",), 1), ((), 0), (("En=2,2", "En=2,3"), 0)],
)
def test_extractor_call_count_follows_unique_source_policy(monkeypatch, student_texts, expected_calls) -> None:
    references, expectations = _case(student_texts, missing_sources=1 if not student_texts else 0)
    import tpstudio.evaluation.student_normalized_errors as module

    original = module.extract_student_normalized_error
    calls = []

    def tracked(text, expectation):
        calls.append((text, expectation))
        return original(text, expectation)

    monkeypatch.setattr(module, "extract_student_normalized_error", tracked)
    StudentNormalizedErrorEvaluator().evaluate(references, expectations)
    assert len(calls) == expected_calls


def test_models_are_immutable_set_api_and_determinism() -> None:
    references, expectations = _case()
    first = StudentNormalizedErrorEvaluator().evaluate(references, expectations)
    second = StudentNormalizedErrorEvaluator().evaluate(references, expectations)
    assert first == second
    item = first.evaluations[0]
    assert tuple(first) == (item,) and len(first) == 1
    assert first.get("comparison") is item
    assert first.for_status(Status.MATCHES_REFERENCE) == (item,)
    assert first.for_reason(Reason.SOURCE_UNAVAILABLE) == ()
    assert first.matches == (item,) and first.differences == first.not_evaluable == ()
    assert first.all_evaluable and not first.has_differences and not first.has_not_evaluable
    with pytest.raises(FrozenInstanceError):
        item.status = Status.NOT_EVALUABLE
    with pytest.raises(FrozenInstanceError):
        first.evaluations = ()


def test_set_rejects_foreign_reference_and_sources() -> None:
    first, references, expectations = _evaluate()
    foreign, _, _ = _evaluate()
    with pytest.raises(ValueError):
        StudentNormalizedErrorEvaluationSet(expectations, references, foreign.evaluations)


def test_public_contract_has_no_diagnostic_feedback_or_judgment() -> None:
    item = _evaluate()[0].evaluations[0]
    for name in ("correct", "student_correct", "diagnostic", "feedback", "score", "penalty", "grade", "interpreted_correctly"):
        assert not hasattr(item, name)
