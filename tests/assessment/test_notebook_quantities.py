from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import nbformat
import pytest

import tpstudio.assessment.notebook_quantities as notebook_module
from tpstudio.assessment import (
    NotebookQuantityAssessmentItem,
    NotebookQuantityAssessmentPipeline,
    NotebookQuantityAssessmentSet,
    NotebookQuantityAssessmentStatus,
    assess_notebook_quantities,
)
from tpstudio.diagnostics import QuantityDiagnosticCode
from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    EvaluationBasis,
    ExpectedQuantity,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
    PresenceRequirement,
    QuantityExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
    UncertaintyQualityExpectationSet,
    UncertaintyQualitySpec,
)
from tpstudio.feedback import french_quantity_feedback_catalog
from tpstudio.notebooks import NotebookBindingResolutionStatus, resolve_notebook_bindings


def _context(*, include_static=True, comparison=True, uncertainty=True):
    productions = [
        ScientificProductionSpec("gravity_dynamic", "g dynamique", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,)),
    ]
    if include_static:
        productions.append(ScientificProductionSpec("gravity_static", "g statique", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,)))
    if comparison:
        productions.append(ScientificProductionSpec("gravity_comparison", "Comparaison", ScientificProductionKind.COMPARISON, (EvaluationBasis.CROSS_PRODUCTION,), depends_on=tuple(p.id for p in productions)))
    plan = ScientificProductionPlan("pendulum", "Pendule", tuple(productions))
    quantities = []
    for production in productions:
        if production.kind is ScientificProductionKind.QUANTITY:
            quantities.append(ExpectedQuantity(
                production.id, "g", canonical_unit="m·s⁻²",
                unit_requirement=PresenceRequirement.REQUIRED,
                uncertainty_requirement=PresenceRequirement.REQUIRED,
            ))
    quantity_set = QuantityExpectationSet(plan, tuple(quantities))
    policy = None
    if uncertainty:
        policy = UncertaintyQualityExpectationSet(
            quantity_set,
            (UncertaintyQualitySpec("gravity_dynamic"),),
        )
    return plan, quantity_set, policy


def _binding(identifier, production_id, kind, value, scope=None):
    return CellProductionBinding(
        identifier, production_id, NotebookCellSelector(kind, value),
        scope or CellTextScope.full_source(),
    )


def _standard_bindings(plan):
    bindings = [
        _binding("dynamic", "gravity_dynamic", NotebookCellSelectorKind.TAG, "answer-gravity-dynamic", CellTextScope.after_marker("Réponse :")),
    ]
    if plan.get("gravity_static") is not None:
        bindings.append(_binding("static", "gravity_static", NotebookCellSelectorKind.CELL_ID, "cell-gravity-static"))
    if plan.get("gravity_comparison") is not None:
        bindings.append(_binding("comparison", "gravity_comparison", NotebookCellSelectorKind.SOURCE_MARKER, "TPSTUDIO: gravity_comparison"))
    return NotebookBindingPlan("bindings", "Bindings", plan, tuple(bindings))


def _cell(source, *, cell_id=None, tags=()):
    cell = nbformat.v4.new_markdown_cell(source, metadata={"tags": list(tags)})
    if cell_id is None:
        cell.pop("id", None)
    else:
        cell.id = cell_id
    return cell


def _notebook(*cells):
    notebook = nbformat.v4.new_notebook()
    notebook.cells = list(cells)
    return notebook


def _business_case(*, static_source="g = 9,8 ± 0,2", catalog=True, uncertainty=True):
    plan, quantities, policy = _context(uncertainty=uncertainty)
    bindings = _standard_bindings(plan)
    notebook = _notebook(
        _cell("Déterminer g.\nRéponse :\ng = (9,7 ± 0,4) m·s⁻²", tags=("answer-gravity-dynamic",)),
        _cell(static_source, cell_id="cell-gravity-static"),
        _cell("TPSTUDIO: gravity_comparison\nRéponse : compatibles"),
    )
    result = assess_notebook_quantities(
        notebook, bindings, quantities, policy,
        french_quantity_feedback_catalog() if catalog else None,
    )
    return result, notebook, bindings, quantities, policy


def test_status_values_are_exact() -> None:
    assert tuple(item.value for item in NotebookQuantityAssessmentStatus) == (
        "assessed", "resolution_failed"
    )


def test_public_api_preserves_a69a_and_exports_five_a69d_objects() -> None:
    import tpstudio.assessment as assessment
    assert assessment.__all__ == [
        "NotebookQuantityAssessmentItem",
        "NotebookQuantityAssessmentPipeline",
        "NotebookQuantityAssessmentSet",
        "NotebookQuantityAssessmentStatus",
        "QuantityAssessmentPipeline",
        "QuantityAssessmentResult",
        "assess_notebook_quantities",
        "assess_quantity_text",
    ]


def test_complete_business_case_keeps_resolution_set_and_assesses_only_quantities() -> None:
    result, _, _, _, _ = _business_case()
    assert len(result.resolution_set) == 3
    assert tuple(item.binding_id for item in result) == ("dynamic", "static")
    assert len(result.assessments) == 2
    assert result.get("comparison") is None
    comparison = result.resolution_set.get("comparison")
    assert comparison is not None and comparison.resolved
    assert result.items[0].assessment is not None
    assert result.items[0].assessment.diagnostics == ()
    assert tuple(item.code for item in result.items[1].diagnostics) == (
        QuantityDiagnosticCode.UNIT_MISSING,
    )
    assert tuple(item.text for item in result.items[1].student_feedback) == (
        "Précisez l’unité de la valeur indiquée.",
    )


def test_item_is_immutable_and_has_derived_properties() -> None:
    item = _business_case()[0].items[1]
    assert item.binding_id == "static" and item.production_id == "gravity_static"
    assert item.assessed and not item.resolution_failed
    assert item.has_diagnostics and item.has_student_feedback
    assert not item.has_teacher_feedback
    with pytest.raises(FrozenInstanceError):
        item.status = NotebookQuantityAssessmentStatus.RESOLUTION_FAILED  # type: ignore[misc]


def test_assessed_item_rejects_incoherent_resolution_production_status_and_assessment() -> None:
    result = _business_case()[0]
    item = result.items[0]
    other = result.items[1]
    for changes in (
        {"resolution": other.resolution},
        {"production_spec": other.production_spec},
        {"status": "assessed"},
        {"assessment": None},
        {"assessment": other.assessment},
    ):
        with pytest.raises((TypeError, ValueError)):
            replace(item, **changes)


def test_item_rejects_non_quantity_production() -> None:
    result, _, bindings, _, _ = _business_case()
    comparison = result.resolution_set.get("comparison")
    production = bindings.production_plan.get("gravity_comparison")
    assert comparison is not None and production is not None
    with pytest.raises(ValueError):
        NotebookQuantityAssessmentItem(
            comparison, production, NotebookQuantityAssessmentStatus.RESOLUTION_FAILED
        )


@pytest.mark.parametrize(
    ("notebook", "binding"),
    [
        (_notebook(), _binding("b", "gravity_dynamic", NotebookCellSelectorKind.CELL_ID, "missing")),
        (_notebook(_cell("x", cell_id="same"), _cell("y", cell_id="same")), _binding("b", "gravity_dynamic", NotebookCellSelectorKind.CELL_ID, "same")),
        (_notebook(_cell("answer", cell_id="target")), _binding("b", "gravity_dynamic", NotebookCellSelectorKind.CELL_ID, "target", CellTextScope.after_marker("M:"))),
        (_notebook(_cell("M:x M:y", cell_id="target")), _binding("b", "gravity_dynamic", NotebookCellSelectorKind.CELL_ID, "target", CellTextScope.after_marker("M:"))),
    ],
)
def test_each_resolution_failure_creates_empty_item(notebook, binding) -> None:
    plan, quantities, _ = _context(include_static=False, comparison=False)
    binding_plan = NotebookBindingPlan("b", "Bindings", plan, (binding,))
    result = assess_notebook_quantities(notebook, binding_plan, quantities)
    item = result.items[0]
    assert item.status is NotebookQuantityAssessmentStatus.RESOLUTION_FAILED
    assert item.assessment is None and item.resolution.failed
    assert item.diagnostics == item.student_feedback == item.teacher_feedback == ()
    assert not item.has_diagnostics and not item.has_student_feedback and not item.has_teacher_feedback


def test_resolved_cell_without_quantity_is_assessed_as_quantity_missing() -> None:
    plan, quantities, _ = _context(include_static=False, comparison=False)
    binding = _binding("b", "gravity_dynamic", NotebookCellSelectorKind.CELL_ID, "target")
    result = assess_notebook_quantities(
        _notebook(_cell("Je n’ai pas obtenu de résultat.", cell_id="target")),
        NotebookBindingPlan("b", "Bindings", plan, (binding,)), quantities,
    )
    item = result.items[0]
    assert item.assessed
    assert tuple(d.code for d in item.diagnostics) == (QuantityDiagnosticCode.QUANTITY_MISSING,)


def test_set_api_preserves_order_and_concatenates_without_deduplication() -> None:
    result = _business_case(static_source="g = 9,8")[0]
    assert tuple(result) == result.items and len(result) == 2
    assert result.get("dynamic") is result.items[0] and result.get("unknown") is None
    assert result.for_production("gravity_dynamic") == (result.items[0],)
    assert result.for_production("gravity_comparison") == ()
    with pytest.raises(ValueError):
        result.for_production("unknown")
    assert result.for_status(NotebookQuantityAssessmentStatus.ASSESSED) == result.assessed
    assert result.resolution_failures == ()
    assert result.all_assessed and not result.has_resolution_failures
    expected = tuple(d for item in result.items for d in item.diagnostics)
    assert result.diagnostics == expected
    assert result.student_feedback == tuple(f for item in result.items for f in item.student_feedback)
    assert result.teacher_feedback == ()
    assert not hasattr(result, "combined_text") and not hasattr(result, "score")


def test_set_is_immutable_and_rejects_missing_foreign_wrong_order_and_non_quantity_items() -> None:
    result = _business_case()[0]
    with pytest.raises(FrozenInstanceError):
        result.items = ()  # type: ignore[misc]
    with pytest.raises(ValueError):
        NotebookQuantityAssessmentSet(result.resolution_set, result.items[:1])
    with pytest.raises(ValueError):
        NotebookQuantityAssessmentSet(result.resolution_set, tuple(reversed(result.items)))
    foreign = _business_case()[0].items[0]
    with pytest.raises(ValueError):
        NotebookQuantityAssessmentSet(result.resolution_set, (foreign, result.items[1]))
    with pytest.raises(TypeError):
        NotebookQuantityAssessmentSet(result.resolution_set, (object(), object()))  # type: ignore[arg-type]


def test_plan_without_quantity_binding_returns_empty_logically_complete_set() -> None:
    comparison = ScientificProductionSpec("comparison", "Comparison", ScientificProductionKind.COMPARISON, (EvaluationBasis.CROSS_PRODUCTION,))
    quantity = ScientificProductionSpec("quantity", "Quantity", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    plan = ScientificProductionPlan("p", "Plan", (quantity, comparison))
    quantities = QuantityExpectationSet(plan, (ExpectedQuantity("quantity", "q", canonical_unit="m"),))
    binding = _binding("comparison-binding", "comparison", NotebookCellSelectorKind.CELL_ID, "target")
    result = assess_notebook_quantities(
        _notebook(_cell("comparison", cell_id="target")),
        NotebookBindingPlan("b", "Bindings", plan, (binding,)), quantities,
    )
    assert len(result.resolution_set) == 1 and result.items == ()
    assert result.all_assessed and not result.has_resolution_failures
    assert result.assessments == result.diagnostics == result.student_feedback == result.teacher_feedback == ()


def test_multiple_bindings_for_one_quantity_are_independent_and_ordered() -> None:
    plan, quantities, _ = _context(include_static=False, comparison=False)
    bindings = (
        _binding("first", "gravity_dynamic", NotebookCellSelectorKind.CELL_ID, "one"),
        _binding("second", "gravity_dynamic", NotebookCellSelectorKind.CELL_ID, "two"),
    )
    result = assess_notebook_quantities(
        _notebook(_cell("g=9 ± 1 m·s⁻²", cell_id="one"), _cell("g=8 ± 1 m·s⁻²", cell_id="two")),
        NotebookBindingPlan("b", "Bindings", plan, bindings), quantities,
    )
    assert tuple(item.binding_id for item in result.for_production("gravity_dynamic")) == ("first", "second")
    assert len(result.assessments) == 2
    assert result.assessments[0] is not result.assessments[1]


def test_same_cell_for_two_quantities_produces_two_assessments() -> None:
    plan, quantities, _ = _context(comparison=False)
    bindings = (
        _binding("dynamic", "gravity_dynamic", NotebookCellSelectorKind.TAG, "shared"),
        _binding("static", "gravity_static", NotebookCellSelectorKind.TAG, "shared"),
    )
    result = assess_notebook_quantities(
        _notebook(_cell("g=9 ± 1 m·s⁻²", tags=("shared",))),
        NotebookBindingPlan("b", "Bindings", plan, bindings), quantities,
    )
    assert len(result.assessments) == 2
    assert result.items[0].resolution.cell == result.items[1].resolution.cell
    assert tuple(a.production_id for a in result.assessments) == ("gravity_dynamic", "gravity_static")


def test_no_catalog_and_no_uncertainty_policy_are_forwarded() -> None:
    result = _business_case(catalog=False, uncertainty=False)[0]
    assert all(assessment.feedback_set is None for assessment in result.assessments)
    assert all(assessment.uncertainty_evaluation is None for assessment in result.assessments)
    assert result.student_feedback == result.teacher_feedback == ()


def test_partial_uncertainty_policy_applies_only_to_configured_production() -> None:
    result = _business_case()[0]
    by_id = {assessment.production_id: assessment for assessment in result.assessments}
    assert by_id["gravity_dynamic"].uncertainty_evaluation is not None
    assert by_id["gravity_static"].uncertainty_evaluation is None


def test_configuration_mismatch_is_rejected_before_resolution_or_assessment(monkeypatch) -> None:
    plan, quantities, _ = _context()
    binding_plan = _standard_bindings(plan)
    other_plan, other_quantities, _ = _context()
    calls = []
    monkeypatch.setattr(notebook_module, "resolve_notebook_bindings", lambda *args: calls.append(args))
    with pytest.raises(ValueError, match="même plan"):
        assess_notebook_quantities(_notebook(), binding_plan, other_quantities)
    assert calls == []
    missing_quantities = QuantityExpectationSet(plan, (quantities.quantities[0],))
    with pytest.raises(ValueError, match="absente"):
        assess_notebook_quantities(_notebook(), binding_plan, missing_quantities)
    assert calls == []


@pytest.mark.parametrize("position", range(5))
def test_pipeline_validates_argument_types(position) -> None:
    plan, quantities, policy = _context()
    args = [_notebook(), _standard_bindings(plan), quantities, policy, french_quantity_feedback_catalog()]
    args[position] = object()
    with pytest.raises(TypeError):
        NotebookQuantityAssessmentPipeline().assess(*args)


def test_calls_a69c_once_and_a69a_once_per_resolved_quantity_with_exact_arguments(monkeypatch) -> None:
    plan, quantities, policy = _context()
    binding_plan = _standard_bindings(plan)
    notebook = _business_case()[1]
    catalog = french_quantity_feedback_catalog()
    original_resolve = notebook_module.resolve_notebook_bindings
    original_assess = notebook_module.assess_quantity_text
    resolution_calls = []
    produced_resolution_sets = []
    assessment_calls = []
    def tracked_resolve(*args):
        resolution_calls.append(args)
        resolution_set = original_resolve(*args)
        produced_resolution_sets.append(resolution_set)
        return resolution_set
    def tracked_assess(*args):
        assessment_calls.append(args)
        return original_assess(*args)
    monkeypatch.setattr(notebook_module, "resolve_notebook_bindings", tracked_resolve)
    monkeypatch.setattr(notebook_module, "assess_quantity_text", tracked_assess)
    result = assess_notebook_quantities(notebook, binding_plan, quantities, policy, catalog)
    assert resolution_calls == [(notebook, binding_plan)]
    assert result.resolution_set is produced_resolution_sets[0]
    assert len(assessment_calls) == 2
    for call, item in zip(assessment_calls, result.items):
        assert call == (item.resolution.text, item.production_id, quantities, policy, catalog)


def test_no_a69a_call_for_resolution_failure_or_non_quantity(monkeypatch) -> None:
    plan, quantities, _ = _context()
    binding_plan = _standard_bindings(plan)
    calls = []
    monkeypatch.setattr(notebook_module, "assess_quantity_text", lambda *args: calls.append(args))
    result = assess_notebook_quantities(_notebook(), binding_plan, quantities)
    assert len(result.items) == 2 and all(item.resolution_failed for item in result)
    assert calls == []


def test_inputs_are_not_mutated_and_two_calls_are_deterministic() -> None:
    result, notebook, bindings, quantities, policy = _business_case()
    catalog = french_quantity_feedback_catalog()
    snapshots = tuple(deepcopy(value) for value in (notebook, bindings, quantities, policy, catalog))
    first = assess_notebook_quantities(notebook, bindings, quantities, policy, catalog)
    second = assess_notebook_quantities(notebook, bindings, quantities, policy, catalog)
    assert first == second
    assert (notebook, bindings, quantities, policy, catalog) == snapshots
    assert result.resolution_set.binding_plan is bindings


def test_convenience_function_only_delegates(monkeypatch) -> None:
    sentinel = object()
    calls = []
    def fake_assess(self, *args):
        calls.append(args)
        return sentinel
    monkeypatch.setattr(NotebookQuantityAssessmentPipeline, "assess", fake_assess)
    plan, quantities, _ = _context()
    notebook = _notebook()
    binding_plan = _standard_bindings(plan)
    assert assess_notebook_quantities(notebook, binding_plan, quantities) is sentinel
    assert calls == [(notebook, binding_plan, quantities, None, None)]
