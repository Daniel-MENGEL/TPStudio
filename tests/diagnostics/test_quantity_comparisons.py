from dataclasses import FrozenInstanceError
from decimal import Decimal

import nbformat
import pytest

from tpstudio.assessment import assess_notebook_quantities
from tpstudio.diagnostics import (
    QuantityComparisonDiagnostic,
    QuantityComparisonDiagnosticBuilder,
    QuantityComparisonDiagnosticCode as Code,
    QuantityComparisonDiagnosticSet,
    QuantityComparisonDiagnosticSource as Source,
    build_quantity_comparison_diagnostics,
)
from tpstudio.evaluation import (
    QuantityComparisonEvaluationStatus as Status,
    evaluate_quantity_comparisons,
)
from tpstudio.expectations import (
    CellProductionBinding, CellTextScope, ComparisonPedagogicalContext,
    EvaluationBasis, ExpectedQuantity, ExpectedQuantityComparison,
    NotebookBindingPlan, NotebookCellSelector, NotebookCellSelectorKind,
    PresenceRequirement, QuantityComparisonExpectationSet,
    QuantityExpectationSet, ScientificProductionKind, ScientificProductionPlan,
    ScientificProductionSpec,
)


def _evaluation(right="x2 = (9.8 ± 0.2) m", *, left="x1 = (9.7 ± 0.4) m", context=ComparisonPedagogicalContext.OPEN):
    left_spec = ScientificProductionSpec("left", "Left", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    right_spec = ScientificProductionSpec("right", "Right", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    comparison = ScientificProductionSpec("comparison", "Comparison", ScientificProductionKind.COMPARISON, (EvaluationBasis.CROSS_PRODUCTION,), depends_on=("left", "right"))
    plan = ScientificProductionPlan("p", "Plan", (left_spec, right_spec, comparison))
    quantities = QuantityExpectationSet(plan, (
        ExpectedQuantity("left", "x1", canonical_unit="m", uncertainty_requirement=PresenceRequirement.REQUIRED),
        ExpectedQuantity("right", "x2", canonical_unit="m", uncertainty_requirement=PresenceRequirement.REQUIRED),
    ))
    bindings = NotebookBindingPlan("b", "Bindings", plan, tuple(
        CellProductionBinding(f"b-{name}", name, NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, name), CellTextScope.full_source())
        for name in ("left", "right")
    ))
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(left, id="left"),
        nbformat.v4.new_markdown_cell(right, id="right"),
    ])
    assessments = assess_notebook_quantities(notebook, bindings, quantities)
    expected = ExpectedQuantityComparison("comparison", "left", "right", pedagogical_context=context, context_note="note")
    expectation_set = QuantityComparisonExpectationSet(plan, quantities, (expected,))
    return evaluate_quantity_comparisons(assessments, expectation_set)


def test_enum_values_and_central_mapping_are_exact() -> None:
    assert tuple(item.value for item in Source) == ("classification", "evaluability")
    assert tuple(item.value for item in Code) == (
        "comparison_moderately_incoherent", "comparison_strongly_incoherent",
        "comparison_not_evaluable",
    )
    assert (Code.COMPARISON_MODERATELY_INCOHERENT.source, Code.COMPARISON_MODERATELY_INCOHERENT.status, Code.COMPARISON_MODERATELY_INCOHERENT.message_key) == (Source.CLASSIFICATION, Status.MODERATELY_INCOHERENT, "comparison.moderately_incoherent")
    assert (Code.COMPARISON_STRONGLY_INCOHERENT.source, Code.COMPARISON_STRONGLY_INCOHERENT.status, Code.COMPARISON_STRONGLY_INCOHERENT.message_key) == (Source.CLASSIFICATION, Status.STRONGLY_INCOHERENT, "comparison.strongly_incoherent")
    assert (Code.COMPARISON_NOT_EVALUABLE.source, Code.COMPARISON_NOT_EVALUABLE.status, Code.COMPARISON_NOT_EVALUABLE.message_key) == (Source.EVALUABILITY, Status.NOT_EVALUABLE, "comparison.not_evaluable")


def test_coherent_comparison_has_no_positive_diagnostic() -> None:
    diagnostic_set = build_quantity_comparison_diagnostics(_evaluation())
    assert tuple(diagnostic_set) == ()
    assert not diagnostic_set.has_diagnostics


@pytest.mark.parametrize(
    ("right", "code"),
    [
        ("x2 = (10.8 ± 0.2) m", Code.COMPARISON_MODERATELY_INCOHERENT),
        ("x2 = (12.0 ± 0.2) m", Code.COMPARISON_STRONGLY_INCOHERENT),
        ("aucun résultat", Code.COMPARISON_NOT_EVALUABLE),
    ],
)
def test_builder_maps_each_non_coherent_status_once(right, code) -> None:
    evaluations = _evaluation(right)
    diagnostic_set = QuantityComparisonDiagnosticBuilder().build(evaluations)
    assert len(diagnostic_set) == 1
    diagnostic = diagnostic_set.get("comparison")
    assert diagnostic is not None and diagnostic.code is code
    assert diagnostic.evaluation is evaluations.evaluations[0]


def test_diagnostic_properties_preserve_evaluation_data() -> None:
    evaluation = _evaluation("x2 = (12.0 ± 0.2) m", context=ComparisonPedagogicalContext.METHOD_LIMITATION_EXPECTED).evaluations[0]
    diagnostic = QuantityComparisonDiagnostic(evaluation, Code.COMPARISON_STRONGLY_INCOHERENT)
    assert diagnostic.production_id == "comparison"
    assert diagnostic.normalized_error == evaluation.normalized_error
    assert diagnostic.pedagogical_context is ComparisonPedagogicalContext.METHOD_LIMITATION_EXPECTED
    assert diagnostic.context_note == "note"
    assert diagnostic.status is Status.STRONGLY_INCOHERENT
    assert diagnostic.not_evaluable_reasons == ()
    with pytest.raises(FrozenInstanceError):
        diagnostic.code = Code.COMPARISON_NOT_EVALUABLE


def test_not_evaluable_keeps_all_reasons_in_one_diagnostic() -> None:
    evaluation = _evaluation(left="x1 = 9.7", right="x2 = 9.8").evaluations[0]
    diagnostic_set = build_quantity_comparison_diagnostics(
        _evaluation(left="x1 = 9.7", right="x2 = 9.8")
    )
    diagnostic = diagnostic_set.diagnostics[0]
    assert len(diagnostic_set) == 1
    assert diagnostic.not_evaluable_reasons == evaluation.not_evaluable_reasons
    assert len(diagnostic.not_evaluable_reasons) == 4


def test_incompatible_code_and_coherent_diagnostic_are_rejected() -> None:
    moderate = _evaluation("x2 = (10.8 ± 0.2) m").evaluations[0]
    with pytest.raises(ValueError):
        QuantityComparisonDiagnostic(moderate, Code.COMPARISON_STRONGLY_INCOHERENT)
    coherent = _evaluation().evaluations[0]
    with pytest.raises(ValueError, match="cohérente"):
        QuantityComparisonDiagnostic(coherent, Code.COMPARISON_NOT_EVALUABLE)


def test_set_validates_identity_completeness_order_and_duplicates() -> None:
    evaluations = _evaluation("x2 = (12.0 ± 0.2) m")
    diagnostic = QuantityComparisonDiagnostic(evaluations.evaluations[0], Code.COMPARISON_STRONGLY_INCOHERENT)
    valid = QuantityComparisonDiagnosticSet(evaluations, [diagnostic])
    assert valid.diagnostics == (diagnostic,)
    with pytest.raises(ValueError):
        QuantityComparisonDiagnosticSet(evaluations, ())
    with pytest.raises(ValueError):
        QuantityComparisonDiagnosticSet(evaluations, (diagnostic, diagnostic))
    foreign = build_quantity_comparison_diagnostics(_evaluation("x2 = (12.0 ± 0.2) m")).diagnostics[0]
    with pytest.raises(ValueError):
        QuantityComparisonDiagnosticSet(evaluations, (foreign,))


def test_set_queries_and_collection_properties() -> None:
    diagnostics = build_quantity_comparison_diagnostics(_evaluation("x2 = (12.0 ± 0.2) m"))
    item = diagnostics.diagnostics[0]
    assert diagnostics.for_code(item.code) == (item,)
    assert diagnostics.for_source(Source.CLASSIFICATION) == (item,)
    assert diagnostics.for_status(Status.STRONGLY_INCOHERENT) == (item,)
    assert diagnostics.strong_incoherences == (item,)
    assert diagnostics.moderate_incoherences == diagnostics.not_evaluable == ()
    assert diagnostics.has_incoherence and diagnostics.has_strong_incoherence
    assert not diagnostics.has_not_evaluable


def test_diagnostic_has_no_presentation_or_scoring_fields() -> None:
    diagnostic = build_quantity_comparison_diagnostics(_evaluation("x2 = (12.0 ± 0.2) m")).diagnostics[0]
    for name in ("text", "audience", "priority", "score", "penalty", "grade"):
        assert not hasattr(diagnostic, name)
