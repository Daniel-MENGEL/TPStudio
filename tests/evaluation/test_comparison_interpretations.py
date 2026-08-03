from decimal import Decimal

import nbformat
import pytest

from tpstudio.assessment import assess_notebook_quantities
from tpstudio.evaluation import (
    ComparisonInterpretationEvaluation,
    ComparisonInterpretationEvaluationStatus as Status,
    ComparisonInterpretationNotEvaluableReason as Reason,
    evaluate_comparison_interpretations, evaluate_quantity_comparisons,
)
from tpstudio.reasoning import ComparisonInterpretationDetection
from tpstudio.expectations import (
    CellProductionBinding, CellTextScope, ComparisonInterpretationExpectationSet,
    ComparisonInterpretationKind as Kind, ComparisonPedagogicalContext as Context,
    EvaluationBasis, ExpectedComparisonInterpretation, ExpectedQuantity,
    ExpectedQuantityComparison, NotebookBindingPlan, NotebookCellSelector,
    NotebookCellSelectorKind, PresenceRequirement, QuantityComparisonExpectationSet,
    QuantityExpectationSet, ScientificProductionKind, ScientificProductionPlan,
    ScientificProductionSpec,
)


def _evaluate(
    texts=("forte",), *, context=Context.OPEN, left="x = (0 ± 0.1) m",
    failures=0, phrases=None,
):
    left_spec = ScientificProductionSpec("left", "Left", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    right_spec = ScientificProductionSpec("right", "Right", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    comparison_spec = ScientificProductionSpec("comparison", "Comparison", ScientificProductionKind.COMPARISON, (EvaluationBasis.CROSS_PRODUCTION,), depends_on=("left", "right"))
    plan = ScientificProductionPlan("p", "Plan", (left_spec, right_spec, comparison_spec))
    quantities = QuantityExpectationSet(plan, (
        ExpectedQuantity("left", "x", canonical_unit="m", uncertainty_requirement=PresenceRequirement.REQUIRED),
        ExpectedQuantity("right", "y", canonical_unit="m", uncertainty_requirement=PresenceRequirement.REQUIRED),
    ))
    cells = [nbformat.v4.new_markdown_cell(left, id="left"), nbformat.v4.new_markdown_cell("y = (1 ± 0.1) m", id="right")]
    bindings = [
        CellProductionBinding("left", "left", NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, "left"), CellTextScope.full_source()),
        CellProductionBinding("right", "right", NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, "right"), CellTextScope.full_source()),
    ]
    for index, text in enumerate(texts):
        identifier = f"c{index}"
        cells.append(nbformat.v4.new_markdown_cell(text, id=identifier))
        bindings.append(CellProductionBinding(identifier, "comparison", NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, identifier), CellTextScope.full_source()))
    for index in range(failures):
        bindings.append(CellProductionBinding(f"missing{index}", "comparison", NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, f"missing{index}"), CellTextScope.full_source()))
    binding_plan = NotebookBindingPlan("b", "Bindings", plan, tuple(bindings))
    assessments = assess_notebook_quantities(nbformat.v4.new_notebook(cells=cells), binding_plan, quantities)
    comparisons = QuantityComparisonExpectationSet(plan, quantities, (
        ExpectedQuantityComparison("comparison", "left", "right", pedagogical_context=context),
    ))
    references = evaluate_quantity_comparisons(assessments, comparisons)
    expected = ExpectedComparisonInterpretation("comparison", phrases or (
        (Kind.COHERENT, "compatible"), (Kind.INCOHERENT, "incohérente"),
        (Kind.STRONGLY_INCOHERENT, "forte"), (Kind.METHOD_LIMITATION, "méthode limitée"),
    ))
    expectations = ComparisonInterpretationExpectationSet(comparisons, (expected,))
    return evaluate_comparison_interpretations(references, expectations), references, expectations


def test_enum_values_are_exact() -> None:
    assert tuple(item.value for item in Status) == ("matches_objective_classification", "contradicts_objective_classification", "partially_matches_objective_classification", "not_evaluable")
    assert tuple(item.value for item in Reason) == ("source_unavailable", "source_ambiguous", "interpretation_missing", "interpretation_ambiguous", "objective_classification_not_evaluable")


@pytest.mark.parametrize(("text", "expected"), [
    ("forte", Status.MATCHES_OBJECTIVE_CLASSIFICATION),
    ("incohérente", Status.PARTIALLY_MATCHES_OBJECTIVE_CLASSIFICATION),
    ("compatible", Status.CONTRADICTS_OBJECTIVE_CLASSIFICATION),
    ("méthode limitée", Status.PARTIALLY_MATCHES_OBJECTIVE_CLASSIFICATION),
])
def test_strong_reference_mappings(text, expected) -> None:
    result, _, _ = _evaluate((text,))
    assert result.evaluations[0].status is expected


def test_method_limitation_expected_changes_only_limitation_mapping() -> None:
    result, _, _ = _evaluate(("méthode limitée",), context=Context.METHOD_LIMITATION_EXPECTED)
    item = result.evaluations[0]
    assert item.status is Status.MATCHES_OBJECTIVE_CLASSIFICATION
    assert item.pedagogical_context is Context.METHOD_LIMITATION_EXPECTED


@pytest.mark.parametrize(("texts", "failures", "reason"), [
    (("aucune",), 0, Reason.INTERPRETATION_MISSING),
    (("forte puis incohérente",), 0, Reason.INTERPRETATION_AMBIGUOUS),
    ((), 1, Reason.SOURCE_UNAVAILABLE),
    (("forte", "forte"), 0, Reason.SOURCE_AMBIGUOUS),
])
def test_not_evaluable_source_and_observation_policies(texts, failures, reason) -> None:
    result, _, _ = _evaluate(texts, failures=failures)
    item = result.evaluations[0]
    assert item.status is Status.NOT_EVALUABLE and reason in item.not_evaluable_reasons
    assert item.observation is None


def test_one_resolved_source_plus_failure_is_usable() -> None:
    result, _, _ = _evaluate(("forte",), failures=1)
    assert result.evaluations[0].matches and len(result.evaluations[0].source_candidates) == 2


def test_overlapping_occurrences_make_evaluation_ambiguous_and_are_canonical() -> None:
    result, _, _ = _evaluate(
        ("ababa",), phrases=((Kind.STRONGLY_INCOHERENT, "aba"),)
    )
    item = result.evaluations[0]
    assert tuple((observation.start, observation.end) for observation in item.detection.observations) == ((0, 3), (2, 5))
    assert item.detection.ambiguous and item.detection.selected_observation is None
    assert item.status is Status.NOT_EVALUABLE
    assert item.not_evaluable_reasons == (Reason.INTERPRETATION_AMBIGUOUS,)

    incomplete = ComparisonInterpretationDetection(
        item.expectation, (item.detection.observations[0],)
    )
    with pytest.raises(ValueError, match="texte résolu"):
        ComparisonInterpretationEvaluation(
            item.expectation, item.reference_evaluation, None,
            item.source_candidates, item.source_resolution, incomplete,
            incomplete.selected_observation,
            Status.MATCHES_OBJECTIVE_CLASSIFICATION,
        )


def test_reference_not_evaluable_reason_is_last() -> None:
    result, _, _ = _evaluate((), failures=1, left="x = 0 m")
    assert result.evaluations[0].not_evaluable_reasons == (
        Reason.SOURCE_UNAVAILABLE, Reason.OBJECTIVE_CLASSIFICATION_NOT_EVALUABLE,
    )


def test_set_api_properties_and_identity() -> None:
    result, references, expectations = _evaluate()
    item = result.get("comparison")
    assert item is result.evaluations[0]
    assert item.expectation is expectations.expectations[0]
    assert item.reference_evaluation is references.evaluations[0]
    assert result.matches == (item,) and result.all_evaluable
    assert not result.has_contradictions and not result.has_partial_matches and not result.has_not_evaluable
    assert item.student_normalized_error_evaluation is None
    assert item.student_normalized_error_status is None
    assert item.source_text_start == 0 and item.source_text_end == 5
