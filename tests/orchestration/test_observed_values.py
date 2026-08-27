from decimal import Decimal

import nbformat
import pytest

from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    EvaluationBasis,
    NotebookCellSelector,
    NotebookCellSelectorKind,
    ScientificProductionKind,
    ScientificProductionSpec,
)
from tpstudio.notebooks import resolve_notebook_bindings
from tpstudio.expectations import NotebookBindingPlan, ScientificProductionPlan
from tpstudio.orchestration import (
    ObservedScalarValue,
    ObservedValueDetection,
    ObservedValueSource,
    code_literal_values,
    detect_observed_values,
)
from tpstudio.projects import snells_laws_teacher_project


@pytest.mark.parametrize(
    ("source", "expected"),
    (("n = 2", "2"), ("n = 1.52", "1.52"), ("n = -1.52", "-1.52"), ("n = 1e-3", "0.001")),
)
def test_safe_code_literals(source: str, expected: str) -> None:
    values = code_literal_values(source, "index", 0)
    assert tuple(item.value for item in values) == (Decimal(expected),)
    assert values[0].source is ObservedValueSource.CODE_LITERAL


@pytest.mark.parametrize("source", ("a = b = 2", "n = a / b", "n = float(1.2)", "n = np.mean(x)", "n = 1 / 0"))
def test_unsafe_or_nonliteral_assignments_are_rejected(source: str) -> None:
    assert code_literal_values(source, "index", 0) == ()


def test_safe_literal_arithmetic_is_read_inside_control_flow() -> None:
    values = code_literal_values(
        "if measured:\n    f_constructeur = 100 / (-6.6)",
        "focal_length",
        0,
        ("f_constructeur",),
        unit="cm",
    )
    assert len(values) == 1
    assert values[0].value == Decimal("100") / Decimal("-6.6")
    assert values[0].unit == "cm"


def _case(cell):
    spec = ScientificProductionSpec("index", "Indice", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    plan = ScientificProductionPlan("p", "Plan", (spec,))
    binding = CellProductionBinding(
        "b", "index", NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, "target"),
        CellTextScope.full_source(),
    )
    notebook = nbformat.v4.new_notebook(cells=[cell])
    resolution = resolve_notebook_bindings(notebook, NotebookBindingPlan("b", "Bindings", plan, (binding,))).resolutions[0]
    return notebook, resolution, spec


@pytest.mark.parametrize(
    ("output", "source"),
    (
        (nbformat.v4.new_output("stream", name="stdout", text="1.52"), ObservedValueSource.TEXT_OUTPUT),
        (nbformat.v4.new_output("execute_result", execution_count=1, data={"text/plain": "1.52"}), ObservedValueSource.EXECUTE_RESULT),
        (nbformat.v4.new_output("display_data", data={"text/plain": "1.52"}), ObservedValueSource.DISPLAY_TEXT),
    ),
)
def test_saved_output_sources_are_retained(output, source) -> None:
    cell = nbformat.v4.new_code_cell("print(n)", id="target", execution_count=1, outputs=[output])
    notebook, resolution, spec = _case(cell)
    detection = detect_observed_values(notebook, resolution, spec)
    assert detection.unique and detection.selected.value == Decimal("1.52")
    assert detection.selected.source is source


def test_distinct_output_values_are_ambiguous() -> None:
    outputs = [nbformat.v4.new_output("stream", name="stdout", text="1.5 1.6")]
    notebook, resolution, spec = _case(nbformat.v4.new_code_cell("print(n)", id="target", outputs=outputs))
    detection = detect_observed_values(notebook, resolution, spec, saved_output_may_be_stale=True)
    assert detection.ambiguous and detection.selected is None
    assert detection.saved_output_may_be_stale


def test_identical_multiple_proofs_select_one_value_without_losing_proofs() -> None:
    outputs = [nbformat.v4.new_output("stream", name="stdout", text="1.5 1.5")]
    notebook, resolution, spec = _case(nbformat.v4.new_code_cell("print(n)", id="target", outputs=outputs))
    detection = detect_observed_values(notebook, resolution, spec)
    assert detection.unique and len(detection.candidates) == 2


def test_code_literal_has_priority_over_saved_output() -> None:
    outputs = [nbformat.v4.new_output("stream", name="stdout", text="9.9")]
    notebook, resolution, spec = _case(nbformat.v4.new_code_cell("n = 1.5", id="target", outputs=outputs))
    detection = detect_observed_values(notebook, resolution, spec)
    assert detection.unique and detection.selected.value == Decimal("1.5")


def test_saved_outputs_can_be_explicitly_ignored() -> None:
    outputs = [nbformat.v4.new_output("stream", name="stdout", text="1.5")]
    notebook, resolution, spec = _case(nbformat.v4.new_code_cell("print(n)", id="target", outputs=outputs))
    detection = detect_observed_values(
        notebook, resolution, spec, inspect_saved_outputs=False
    )
    assert detection.absent


def test_labelled_output_ignores_numbers_from_a_separate_figure_display() -> None:
    project = snells_laws_teacher_project()
    expectation = project.quantity_expectation_set.get("regression_slope")
    production = project.scientific_production_plan.get("regression_slope")
    cell = nbformat.v4.new_code_cell("print(a)", id="target", outputs=[
        nbformat.v4.new_output(
            "display_data", data={"text/plain": "<Figure size 700x450 with 1 Axes>"}
        ),
        nbformat.v4.new_output("stream", name="stdout", text="Pente a = 1.48\n"),
    ])
    notebook, resolution, _ = _case(cell)
    detection = detect_observed_values(
        notebook, resolution, production, expectation=expectation
    )
    assert detection.unique
    assert detection.selected.value == Decimal("1.48")


def test_descriptive_symbol_wins_over_repeated_single_letter_symbol() -> None:
    project = snells_laws_teacher_project()
    expectation = project.quantity_expectation_set.get("regression_slope")
    production = project.scientific_production_plan.get("regression_slope")
    expectation = type(expectation)(
        expectation.production_id,
        "a",
        ("Pente a",),
        None,
        (),
        expectation.unit_requirement,
        expectation.uncertainty_requirement,
        expectation.uncertainty_justification_requirement,
    )
    cell = nbformat.v4.new_code_cell("print(a)", id="target", outputs=[
        nbformat.v4.new_output(
            "stream", name="stdout", text="Pente a = 1.48\nValeur déduite de a = 9.9\n"
        )
    ])
    notebook, resolution, _ = _case(cell)
    detection = detect_observed_values(
        notebook, resolution, production, expectation=expectation
    )
    assert detection.unique
    assert detection.selected.value == Decimal("1.48")


def _priority_detection(markdown: str, code: str, output: str = ""):
    project = snells_laws_teacher_project()
    code_cell = nbformat.v4.new_code_cell("n=1/np.sin(il)\n" + code, execution_count=1)
    if output:
        code_cell.outputs = [nbformat.v4.new_output(
            "execute_result", execution_count=1, data={"text/plain": output}
        )]
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(
            "### Résultat — Première méthode de mesure de l'indice\n" + markdown
        ),
        code_cell,
    ])
    resolutions = resolve_notebook_bindings(notebook, project.notebook_binding_plan)
    expectation = project.quantity_expectation_set.get("direct_index")
    production = project.scientific_production_plan.get("direct_index")
    return detect_observed_values(
        notebook,
        resolutions.for_production("direct_index")[0],
        production,
        expectation=expectation,
        associated_resolutions=resolutions.for_production("direct_index_relation"),
    )


def test_priority_is_text_then_code_then_output_with_all_proofs_retained() -> None:
    detection = _priority_detection("n = 1.50", "n = 1.60", "1.70")
    assert detection.selected.source is ObservedValueSource.MARKDOWN_TEXT
    assert tuple(item.source for item in detection.candidates) == (
        ObservedValueSource.MARKDOWN_TEXT,
        ObservedValueSource.CODE_LITERAL,
        ObservedValueSource.EXECUTE_RESULT,
    )


def test_ambiguous_priority_tier_blocks_lower_tiers() -> None:
    detection = _priority_detection(
        "n = 1.50 puis n = 1.51", "n = 1.60", "1.70"
    )
    assert detection.ambiguous and detection.selected is None


def _candidate(spec, source, value, unit, proof):
    return ObservedScalarValue(
        spec.id, source, Decimal(value), unit, 0, proof
    )


def test_same_value_and_absent_unit_keep_all_concordant_proofs() -> None:
    spec = _case(nbformat.v4.new_code_cell("n = 1", id="target"))[2]
    candidates = (
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "1.52", None, "first"),
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "1.52", None, "second"),
    )
    detection = ObservedValueDetection(spec, candidates, candidates[0])
    assert detection.unique and detection.selected is candidates[0]
    assert detection.candidates == candidates


def test_same_value_with_absent_and_present_unit_is_ambiguous() -> None:
    spec = _case(nbformat.v4.new_code_cell("n = 1", id="target"))[2]
    candidates = (
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "1.52", None, "plain"),
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "1.52", "m", "metre"),
    )
    detection = ObservedValueDetection(spec, candidates, None)
    assert detection.ambiguous and detection.selected is None


def test_same_value_with_different_units_is_ambiguous() -> None:
    spec = _case(nbformat.v4.new_code_cell("n = 1", id="target"))[2]
    candidates = (
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "1.0", "m", "metre"),
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "1.0", "cm", "centimetre"),
    )
    assert ObservedValueDetection(spec, candidates, None).ambiguous


def test_different_values_with_same_unit_are_ambiguous() -> None:
    spec = _case(nbformat.v4.new_code_cell("n = 1", id="target"))[2]
    candidates = (
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "1.0", "m", "one"),
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "2.0", "m", "two"),
    )
    assert ObservedValueDetection(spec, candidates, None).ambiguous


def test_different_output_types_with_same_identity_are_concordant() -> None:
    spec = _case(nbformat.v4.new_code_cell("n = 1", id="target"))[2]
    candidates = (
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "1.52", None, "execute"),
        _candidate(spec, ObservedValueSource.DISPLAY_TEXT, "1.52", None, "display"),
    )
    detection = ObservedValueDetection(spec, candidates, candidates[0])
    assert detection.unique and detection.candidates == candidates


def test_different_output_types_with_different_units_are_ambiguous() -> None:
    spec = _case(nbformat.v4.new_code_cell("n = 1", id="target"))[2]
    candidates = (
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "1.52", "m", "execute"),
        _candidate(spec, ObservedValueSource.DISPLAY_TEXT, "1.52", "cm", "display"),
    )
    assert ObservedValueDetection(spec, candidates, None).ambiguous


def test_manual_detection_rejects_selected_when_units_diverge() -> None:
    spec = _case(nbformat.v4.new_code_cell("n = 1", id="target"))[2]
    candidates = (
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "1.52", None, "plain"),
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "1.52", "m", "metre"),
    )
    with pytest.raises(ValueError):
        ObservedValueDetection(spec, candidates, candidates[0])


def test_manual_detection_rejects_none_for_concordant_identity() -> None:
    spec = _case(nbformat.v4.new_code_cell("n = 1", id="target"))[2]
    candidates = (
        _candidate(spec, ObservedValueSource.EXECUTE_RESULT, "1.52", None, "first"),
        _candidate(spec, ObservedValueSource.DISPLAY_TEXT, "1.52", None, "second"),
    )
    with pytest.raises(ValueError):
        ObservedValueDetection(spec, candidates, None)
