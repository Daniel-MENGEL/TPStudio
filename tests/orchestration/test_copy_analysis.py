from decimal import Decimal
from pathlib import Path

import nbformat
import pytest

from tpstudio.evaluation import (
    ComparisonInterpretationEvaluationStatus,
    ComparisonJustificationEvaluationStatus,
    QuantityComparisonNotEvaluableReason,
)
from tpstudio.feedback import FeedbackAudience
from tpstudio.orchestration import (
    CopyAnalysisOptions,
    NotebookCopySource,
    SnellsLawsCopyAnalyzer,
    ObservedValueSource,
    analyze_snells_laws_copy,
    summarize_copy_analysis,
)
from tpstudio.projects import snells_laws_teacher_project


def _notebook(*, placeholder=False, error=False, inverted_graph=False, omit_marker=None, duplicate_marker=None):
    project = snells_laws_teacher_project()
    markers = []
    for binding in project.notebook_binding_plan:
        marker = binding.selector.value
        if marker not in markers and marker != omit_marker:
            markers.append(marker)
    cells = []
    for marker in markers:
        source = marker
        cell_type = (
            "markdown" if marker.startswith("###")
            else "code" if marker.startswith(("#", "il=", "i1 =", "i2 =", "n=", "En="))
            else "markdown"
        )
        if marker == "### Résultat — Première méthode de mesure de l'indice":
            source += "\nn = (1.50 ± 0.05)"
        elif marker == "### Résultat — Seconde méthode de mesure de l'indice":
            source += "\nn = (1.52 ± 0.05)\nEn = 0,28. Comme En < 2, Les mesures sont cohérentes"
        elif marker == "# Méthode statistique":
            source += "\nn = (1.51 ± 0.05)"
        elif marker == "### Comparaison des résultats obtenus":
            source += "\nEn = 0,14. Comme En < 2, les résultats sont cohérents avec leurs incertitudes"
        elif marker == "# Vérification graphique":
            x, y = ("np.sin(i1)", "np.sin(i2)") if inverted_graph else ("np.sin(i2)", "np.sin(i1)")
            source += f"\nplt.plot({x}, {y})\nplt.xlabel('sin(i2)')\nplt.ylabel('sin(i1)')\na = np.polyfit({x}, {y}, 1)"
        elif marker == "### Conclusion / bilan":
            source += "\nConclusion finale distincte. Limites de la méthode."
        if cell_type == "code":
            cell = nbformat.v4.new_code_cell(source, execution_count=1)
        else:
            cell = nbformat.v4.new_markdown_cell(source)
        cells.append(cell)
        if marker == duplicate_marker:
            cells.append(nbformat.v4.new_markdown_cell(source))
    if placeholder:
        cells.append(nbformat.v4.new_code_cell("unfinished = ?", execution_count=None))
    if error:
        failing = nbformat.v4.new_code_cell("raise ValueError", execution_count=1)
        failing.outputs = [nbformat.v4.new_output("error", ename="ValueError", evalue="x", traceback=[])]
        cells.append(failing)
    return nbformat.v4.new_notebook(cells=cells)


def _analyze(tmp_path: Path, notebook=None, options=None):
    path = tmp_path / "copy"
    nbformat.write(notebook or _notebook(), path)
    before = path.read_bytes()
    result = analyze_snells_laws_copy(
        NotebookCopySource("synthetic", "Copie synthétique", path), options=options
    )
    assert path.read_bytes() == before
    return result


def _cell_with(notebook, marker: str):
    return next(cell for cell in notebook.cells if marker in cell.source)


def _quantity_value(result, production_id: str):
    item = result.quantity_evaluations.for_production(production_id)[0]
    return item.assessment.selected_observation.value if item.assessment.selected_observation else None


def test_synthetic_copy_runs_all_declared_chains_read_only(tmp_path: Path) -> None:
    result = _analyze(tmp_path)
    assert len(result.production_resolutions) == 19
    assert len(result.production_resolutions.resolved) == 19
    assert len(result.quantity_comparison_evaluations) == 2
    assert len(result.student_normalized_error_evaluations) == 2
    assert len(result.comparison_interpretation_evaluations) == 2
    assert len(result.comparison_justification_evaluations) == 2
    assert result.final_conclusion.unique
    assert "Conclusion finale distincte" in result.final_conclusion.text
    assert "path=" not in repr(result)


def test_incomplete_code_and_saved_error_require_review_without_global_failure(tmp_path: Path) -> None:
    result = _analyze(tmp_path, _notebook(placeholder=True, error=True))
    assert result.has_placeholders and result.has_technical_errors
    assert len(result.quantity_comparison_evaluations) == 2
    assert result.requires_human_review


def test_inverted_graph_does_not_prevent_comparisons(tmp_path: Path) -> None:
    result = _analyze(tmp_path, _notebook(inverted_graph=True))
    assert result.has_graph_issues
    assert len(result.quantity_comparison_evaluations) == 2


def test_missing_production_is_structured(tmp_path: Path) -> None:
    result = _analyze(tmp_path, _notebook(omit_marker="# Méthode statistique"))
    assert result.has_missing_productions and result.requires_human_review
    assert len(result.comparison_interpretation_evaluations) == 2


def test_ambiguous_production_is_not_selected(tmp_path: Path) -> None:
    marker = "### Comparaison des résultats obtenus"
    result = _analyze(tmp_path, _notebook(duplicate_marker=marker))
    resolution = result.production_resolutions.get("compare_geometric_regression")
    assert resolution.status.value == "ambiguous"
    assert result.has_ambiguous_productions


def test_final_conclusion_remains_separate_from_last_interpretation(tmp_path: Path) -> None:
    result = _analyze(tmp_path)
    assert not hasattr(result.final_conclusion, "status")
    assert result.final_conclusion.text != result.comparison_interpretation_evaluations.evaluations[-1].source_resolution.text


def test_options_can_disable_diagnostics_and_feedback(tmp_path: Path) -> None:
    result = _analyze(tmp_path, options=CopyAnalysisOptions(build_diagnostics=False))
    assert result.diagnostics == () and result.feedback == ()
    result = _analyze(tmp_path, options=CopyAnalysisOptions(render_feedback=False))
    assert result.diagnostics and result.feedback == ()


def test_options_can_ignore_saved_outputs(tmp_path: Path) -> None:
    result = _analyze(tmp_path, options=CopyAnalysisOptions(inspect_saved_outputs=False))
    assert result.options.inspect_saved_outputs is False


@pytest.mark.parametrize(
    ("options", "audience"),
    (
        (CopyAnalysisOptions(teacher_feedback=False), FeedbackAudience.STUDENT),
        (CopyAnalysisOptions(student_feedback=False), FeedbackAudience.TEACHER),
    ),
)
def test_feedback_audience_options_filter_items(tmp_path: Path, options, audience) -> None:
    result = _analyze(tmp_path, _notebook(omit_marker="# Méthode statistique"), options)
    assert all(item.audience is audience for item in result.feedback)


def test_execute_option_is_explicitly_refused(tmp_path: Path) -> None:
    path = tmp_path / "copy"
    nbformat.write(_notebook(), path)
    with pytest.raises(NotImplementedError):
        SnellsLawsCopyAnalyzer().analyze(
            NotebookCopySource("synthetic", "Synthétique", path),
            options=CopyAnalysisOptions(execute_notebook=True),
        )


def test_analysis_and_summary_are_deterministic_and_private(tmp_path: Path) -> None:
    path = tmp_path / "copy"
    nbformat.write(_notebook(), path)
    source = NotebookCopySource("synthetic", "Synthétique", path)
    first = analyze_snells_laws_copy(source)
    second = analyze_snells_laws_copy(source)
    assert first == second
    summary = summarize_copy_analysis(first)
    assert str(tmp_path) not in summary
    assert "Projet : snells-laws-mvp" in summary
    assert "Revue humaine :" in summary


def test_interpretation_and_justification_statuses_remain_independent(tmp_path: Path) -> None:
    result = _analyze(tmp_path)
    assert all(item.observed_kind is not None for item in result.comparison_interpretation_evaluations)
    assert all(
        item.status is ComparisonInterpretationEvaluationStatus.NOT_EVALUABLE
        for item in result.comparison_interpretation_evaluations
    )
    assert all(
        item.status is ComparisonJustificationEvaluationStatus.COMPLETE
        for item in result.comparison_justification_evaluations
    )


def test_code_literal_is_really_adapted_into_quantity_assessment(tmp_path: Path) -> None:
    notebook = _notebook()
    _cell_with(notebook, "### Résultat — Première méthode").source = (
        "### Résultat — Première méthode de mesure de l'indice\nValeur dans le code."
    )
    _cell_with(notebook, "n=1/np.sin(il)").source += "\nn = 1.52"
    result = _analyze(tmp_path, notebook)
    detection = result.get_observed_value_detection("direct_index")
    assert detection.selected.value == Decimal("1.52")
    assert detection.selected.source is ObservedValueSource.CODE_LITERAL
    assert _quantity_value(result, "direct_index") == Decimal("1.52")


def test_execute_result_is_really_adapted_and_keeps_stale_provenance(tmp_path: Path) -> None:
    notebook = _notebook()
    _cell_with(notebook, "### Résultat — Première méthode").source = (
        "### Résultat — Première méthode de mesure de l'indice\nValeur dans l'output."
    )
    code = _cell_with(notebook, "n=1/np.sin(il)")
    code.execution_count = None
    code.outputs = [nbformat.v4.new_output(
        "execute_result", execution_count=1, data={"text/plain": "1.52"}
    )]
    result = _analyze(tmp_path, notebook)
    detection = result.get_observed_value_detection("direct_index")
    assert detection.selected.source is ObservedValueSource.EXECUTE_RESULT
    assert detection.saved_output_may_be_stale
    assert _quantity_value(result, "direct_index") == Decimal("1.52")


def test_text_value_has_priority_over_different_code_literal(tmp_path: Path) -> None:
    notebook = _notebook()
    _cell_with(notebook, "### Résultat — Première méthode").source = (
        "### Résultat — Première méthode de mesure de l'indice\nn = 1.50"
    )
    _cell_with(notebook, "n=1/np.sin(il)").source += "\nn = 1.60"
    result = _analyze(tmp_path, notebook)
    detection = result.get_observed_value_detection("direct_index")
    assert detection.selected.source is ObservedValueSource.MARKDOWN_TEXT
    assert {item.value for item in detection.candidates} >= {Decimal("1.50"), Decimal("1.60")}
    assert _quantity_value(result, "direct_index") == Decimal("1.50")


def test_ambiguous_text_blocks_code_fallback(tmp_path: Path) -> None:
    notebook = _notebook()
    _cell_with(notebook, "### Résultat — Première méthode").source = (
        "### Résultat — Première méthode de mesure de l'indice\nn = 1.50 puis n = 1.51"
    )
    _cell_with(notebook, "n=1/np.sin(il)").source += "\nn = 1.60"
    result = _analyze(tmp_path, notebook)
    detection = result.get_observed_value_detection("direct_index")
    assert detection.ambiguous and detection.selected is None
    assert _quantity_value(result, "direct_index") is None


def test_ambiguous_code_blocks_output_fallback(tmp_path: Path) -> None:
    notebook = _notebook()
    _cell_with(notebook, "### Résultat — Première méthode").source = (
        "### Résultat — Première méthode de mesure de l'indice\nValeur dans le code."
    )
    code = _cell_with(notebook, "n=1/np.sin(il)")
    code.source += "\nn = 1.50\nn = 1.60"
    code.outputs = [nbformat.v4.new_output(
        "execute_result", execution_count=1, data={"text/plain": "1.55"}
    )]
    result = _analyze(tmp_path, notebook)
    detection = result.get_observed_value_detection("direct_index")
    assert detection.ambiguous and detection.selected is None
    assert _quantity_value(result, "direct_index") is None


def test_output_values_and_uncertainties_reach_a70_comparison(tmp_path: Path) -> None:
    notebook = _notebook()
    for marker, code_marker, text in (
        ("### Résultat — Première méthode", "n=1/np.sin(il)", "n = (1.50 ± 0.05)"),
        ("### Résultat — Seconde méthode", "n=np.sin(i1)/np.sin(i2)", "n = (1.52 ± 0.05)"),
    ):
        response = _cell_with(notebook, marker)
        heading = response.source.splitlines()[0]
        response.source = heading + "\nValeur dans l'output."
        code = _cell_with(notebook, code_marker)
        code.outputs = [nbformat.v4.new_output(
            "execute_result", execution_count=1, data={"text/plain": text}
        )]
    result = _analyze(tmp_path, notebook)
    assert _quantity_value(result, "direct_index") == Decimal("1.50")
    assert _quantity_value(result, "geometric_index") == Decimal("1.52")
    comparison = result.quantity_comparison_evaluations.get("compare_direct_geometric")
    assert comparison.left_value == Decimal("1.50")
    assert comparison.right_value == Decimal("1.52")
    assert QuantityComparisonNotEvaluableReason.LEFT_OBSERVATION_MISSING not in comparison.not_evaluable_reasons
    assert QuantityComparisonNotEvaluableReason.RIGHT_OBSERVATION_MISSING not in comparison.not_evaluable_reasons
    assert comparison.not_evaluable_reasons == (
        QuantityComparisonNotEvaluableReason.LEFT_UNIT_MISSING,
        QuantityComparisonNotEvaluableReason.RIGHT_UNIT_MISSING,
    )


def test_same_value_with_different_units_blocks_assessment_and_fallback(tmp_path: Path) -> None:
    notebook = _notebook()
    cell = _cell_with(notebook, "il= ? #degrés")
    cell.outputs = [
        nbformat.v4.new_output(
            "execute_result", execution_count=1,
            data={"text/plain": "i_l = 30 °"},
        ),
        nbformat.v4.new_output(
            "display_data", data={"text/plain": "i_l = 30 deg"},
        ),
    ]
    result = _analyze(tmp_path, notebook)
    detection = result.get_observed_value_detection("critical_angle")
    assert detection.ambiguous and detection.selected is None
    assert {item.unit for item in detection.candidates} == {"°", "deg"}
    assert _quantity_value(result, "critical_angle") is None
    assert result.requires_human_review


def test_identical_value_and_unit_proofs_remain_selectable_in_analysis(tmp_path: Path) -> None:
    notebook = _notebook()
    cell = _cell_with(notebook, "il= ? #degrés")
    cell.outputs = [
        nbformat.v4.new_output(
            "execute_result", execution_count=1,
            data={"text/plain": "i_l = 30 deg"},
        ),
        nbformat.v4.new_output(
            "display_data", data={"text/plain": "i_l = 30 deg"},
        ),
    ]
    result = _analyze(tmp_path, notebook)
    detection = result.get_observed_value_detection("critical_angle")
    assert detection.unique and detection.selected is detection.candidates[0]
    assert len(detection.candidates) == 2
    item = result.quantity_evaluations.for_production("critical_angle")[0]
    observation = item.assessment.selected_observation
    assert observation.value == Decimal("30") and observation.unit == "deg"
