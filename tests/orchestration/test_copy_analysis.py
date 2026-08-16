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
from tpstudio.graph_analysis import GraphScientificClassification
from tpstudio.regression import RegressionTargetKind
from tpstudio.projects import snells_laws_teacher_project
from tpstudio.reporting import build_teacher_copy_report
from tpstudio.protocol import (
    ProtocolStatus,
    prepare_notebook_with_protocol_cells,
    snells_laws_manipulations,
)
from tpstudio.interpretation import InterpretationClassification
from tpstudio.annotation import build_annotation_plan


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
    assert len(result.regression_observations) == 1
    assert result.regression_observations[0].method.value == "numpy_polyfit"
    assert result.regression_observations[0].x_expression == "np.sin(i2)"
    assert result.regression_observations[0].y_expression == "np.sin(i1)"
    assert "path=" not in repr(result)


def test_multiple_measured_graph_series_reach_copy_analysis_result(tmp_path: Path) -> None:
    notebook = _notebook()
    graph_cell = _cell_with(notebook, "# Vérification graphique")
    graph_cell.source = (
        "# Vérification graphique\n"
        "plt.plot([0, 1, 2, 3, 4, 5], [1, 3, 5, 7, 9, 11], label='Mesures')\n"
        "plt.plot([0, 1, 2, 3, 4, 5], [0, 1, 4, 9, 16, 25], label='Mesures')\n"
    )
    result = _analyze(tmp_path, notebook)
    assert len(result.graph_series_data) == 2
    assert len(result.graph_analyses) == 2
    assert [item.series_id for item in result.graph_series_data] == [
        item.series_id for item in result.graph_analyses
    ]
    assert [item.cell_id for item in result.graph_series_data] == [
        item.cell_id for item in result.graph_analyses
    ]
    assert [item.cell_index_snapshot for item in result.graph_series_data] == [
        item.cell_index_snapshot for item in result.graph_analyses
    ]
    assert result.graph_analyses[0].scientific_classification is GraphScientificClassification.LINEAR_COMPATIBLE
    assert result.graph_analyses[1].scientific_classification is GraphScientificClassification.CLEARLY_NONLINEAR


def test_regression_without_graph_expectation_reaches_copy_result(tmp_path: Path) -> None:
    notebook = _notebook()
    graph_cell = _cell_with(notebook, "# Vérification graphique")
    graph_cell.source = "# Vérification graphique"
    notebook.cells.append(nbformat.v4.new_code_cell(
        "plt.plot(x, y, 'o', label='Mesures')\na, b = np.polyfit(x, y, 1)"
    ))
    result = _analyze(tmp_path, notebook)
    assert len(result.regression_observations) == 1
    assert result.regression_observations[0].target_kind is RegressionTargetKind.TUPLE
    assert result.regression_observations[0].x_expression == "x"
    assert result.graph_series_data == ()
    assert len(result.all_graph_series_data) == 1
    assert result.all_graph_series_data[0].role.value == "measured"
    assert result.regression_series_matches[0].status.value == "exact"
    assert result.regression_series_matches[0].matched_series_id == result.all_graph_series_data[0].series_id


def test_snell_like_global_series_matches_structurally_without_expectation(tmp_path: Path) -> None:
    notebook = _notebook()
    graph_cell = _cell_with(notebook, "# Vérification graphique")
    graph_cell.source = "# Vérification graphique"
    notebook.cells.append(nbformat.v4.new_code_cell(
        "plt.plot(np.sin(i2), np.sin(i1), 'bo', label='Points experimentaux')\n"
        "a, b = np.polyfit(np.sin(i2), np.sin(i1), 1)"
    ))
    result = _analyze(tmp_path, notebook)
    assert result.graph_series_data == ()
    assert result.all_graph_series_data[0].role.value == "measured"
    assert result.regression_series_matches[0].status.value == "exact"


def test_snell_like_dtype_float_pipeline_is_evaluable(tmp_path: Path) -> None:
    notebook = _notebook()
    graph_cell = _cell_with(notebook, "# Vérification graphique")
    graph_cell.source = (
        "# Vérification graphique\n"
        "i1 = np.array([0.0, 5.0, 10.0, 15.0, 20.0], dtype=float)\n"
        "i2 = np.array([0.0, 3.5, 7.0, 10.0, 13.0], dtype=float)\n"
        "i1 = i1*np.pi/180\n"
        "i2 = i2*np.pi/180\n"
        "sini1 = np.sin(i1)\n"
        "sini2 = np.sin(i2)\n"
        "plt.plot(sini2, sini1, 'bo', label='Points experimentaux')\n"
        "a, b = np.polyfit(sini2, sini1, 1)\n"
    )
    result = _analyze(tmp_path, notebook)
    measured = result.all_graph_series_data[0]
    assert measured.technical_status.value == "extracted"
    assert measured.n_points == 5
    assert result.regression_series_matches[0].status.value == "exact"
    assert result.regression_model_analyses[0].technical_status.value == "evaluable"


def test_global_series_match_is_reused_by_model_analysis_without_expectation(tmp_path: Path) -> None:
    notebook = _notebook()
    graph_cell = _cell_with(notebook, "# Vérification graphique")
    graph_cell.source = "# Vérification graphique"
    notebook.cells.append(nbformat.v4.new_code_cell(
        "x = [0.0, 1.0, 2.0]\n"
        "y = [1.0, 3.0, 5.0]\n"
        "plt.plot(x, y, 'o', label='Mesures')\n"
        "a, b = np.polyfit(x, y, 1)"
    ))
    result = _analyze(tmp_path, notebook)
    assert result.graph_series_data == ()
    global_series = result.all_graph_series_data[0]
    match = result.regression_series_matches[0]
    model = result.regression_model_analyses[0]
    assert match.status.value == "exact"
    assert match.matched_series_id == global_series.series_id
    assert model.technical_status.value == "evaluable"
    assert model.series_id == global_series.series_id
    assert model.coefficients is not None
    assert model.predicted_y_values is not None
    assert "serie_appariee_absente" not in model.diagnostics


def test_regressions_in_several_cells_keep_global_order(tmp_path: Path) -> None:
    notebook = _notebook()
    graph_cell = _cell_with(notebook, "# Vérification graphique")
    graph_cell.source = "# Vérification graphique"
    notebook.cells.extend([
        nbformat.v4.new_code_cell("p1 = np.polyfit(x1, y1, 1)"),
        nbformat.v4.new_code_cell("np.polyfit(x2, y2, 2)"),
        nbformat.v4.new_code_cell("r = linregress(x3, y3)"),
    ])
    result = _analyze(tmp_path, notebook)
    observations = result.regression_observations
    assert len(observations) == 3
    assert [item.degree for item in observations] == [1, 2, 1]
    assert [item.target_kind for item in observations] == [
        RegressionTargetKind.SINGLE, RegressionTargetKind.NONE, RegressionTargetKind.SINGLE,
    ]
    assert [item.cell_index_snapshot for item in observations] == sorted(
        item.cell_index_snapshot for item in observations
    )


def test_regression_and_graph_in_separate_cells_are_kept_separate(tmp_path: Path) -> None:
    notebook = _notebook()
    graph_cell = _cell_with(notebook, "# Vérification graphique")
    graph_cell.source = "# Vérification graphique\nplt.plot(t, z, 'o')"
    notebook.cells.append(nbformat.v4.new_code_cell("a, b, c = np.polyfit(t, z, 2)"))
    result = _analyze(tmp_path, notebook)
    assert len(result.regression_observations) == 1
    assert result.regression_observations[0].degree == 2
    assert len(result.graph_series_data) == 1


def test_global_plotted_series_include_cells_without_graph_expectation(tmp_path: Path) -> None:
    notebook = _notebook()
    graph_cell = _cell_with(notebook, "# Vérification graphique")
    graph_cell.source = "# Vérification graphique\nplt.plot([0, 1, 2], [1, 2, 3], label='Mesures')"
    notebook.cells.append(nbformat.v4.new_code_cell("plt.plot([0, 1, 2], [1, 2, 3], label='fit')"))
    result = _analyze(tmp_path, notebook)
    assert len(result.graph_series_data) == 1
    assert len(result.all_graph_series_data) == 2
    assert result.all_graph_series_data[1].role.value == "fit"
    assert result.all_graph_series_data[1].cell_index_snapshot == len(notebook.cells) - 1


def test_prepared_protocol_cells_are_evaluated_without_global_scan(tmp_path: Path) -> None:
    notebook = prepare_notebook_with_protocol_cells(_notebook(), snells_laws_manipulations())
    for cell in notebook.cells:
        if cell.metadata.get("tpstudio", {}).get("role") == "protocol_response":
            cell.source = cell.source + (
                "\n\nNous plaçons le disque gradué, alignons le rayon et relevons "
                "plusieurs angles dans un tableau."
            )
    result = _analyze(tmp_path, notebook)
    assert [item.status for item in result.protocol_evaluations] == [
        ProtocolStatus.PRESENT,
        ProtocolStatus.PRESENT,
        ProtocolStatus.PRESENT,
    ]


def test_conclusion_response_reaches_analysis_report_and_annotation(tmp_path: Path) -> None:
    notebook = _notebook()
    response = nbformat.v4.new_markdown_cell(
        "Nous avons déterminé les valeurs obtenues. Les résultats sont compatibles avec la théorie, "
        "ce qui confirme le modèle dans les limites expérimentales.",
        metadata={"tpstudio": {"role": "conclusion_response", "expectation_id": "conclusion-main"}},
    )
    notebook.cells.append(response)
    result = _analyze(tmp_path, notebook)
    assert result.conclusion_evaluations[0].status is ProtocolStatus.PRESENT
    report = build_teacher_copy_report(result)
    assert not any(item.category.value == "conclusion" for item in report.diagnostics)
    plan = build_annotation_plan(result)
    assert any(item.target_cell_index == len(notebook.cells) - 1 for item in plan.annotations)


def test_missing_conclusion_reaches_conclusion_category_and_not_evaluable_is_safe(tmp_path: Path) -> None:
    notebook = _notebook()
    notebook.cells.append(nbformat.v4.new_markdown_cell(
        "...", metadata={"tpstudio": {"role": "conclusion_response", "expectation_id": "conclusion-main"}}
    ))
    result = _analyze(tmp_path, notebook)
    report = build_teacher_copy_report(result)
    assert any(item.category.value == "conclusion" for item in report.diagnostics)
    ambiguous = nbformat.v4.new_markdown_cell(
        "Conclusion", metadata={"tpstudio": {"role": "conclusion_response", "expectation_id": "conclusion-2"}}
    )
    notebook.cells.append(ambiguous)
    result = _analyze(tmp_path, notebook)
    assert [item.status for item in result.conclusion_evaluations] == [
        ProtocolStatus.MISSING, ProtocolStatus.PRESENT
    ]


def test_ambiguous_interpretation_reaches_teacher_report_without_student_teacher_text(tmp_path: Path) -> None:
    notebook = _notebook()
    notebook.cells.append(nbformat.v4.new_markdown_cell(
        "L'écart est faible, donc c'est bon.",
        metadata={"tpstudio": {"role": "interpretation_response", "expectation_id": "interp-main"}},
    ))
    result = _analyze(tmp_path, notebook)
    evaluation = result.interpretation_response_evaluations[0]
    assert evaluation.classification is InterpretationClassification.AMBIGUOUS
    assert evaluation.requires_human_review is True
    report = build_teacher_copy_report(result)
    assert any(item.category.value == "interpretation" for item in report.diagnostics)
    assert report.human_review.required is True
    plan = build_annotation_plan(result)
    assert not any("revue humaine" in annotation.message.lower() for annotation in plan.annotations)
    assert not any("protocole" in getattr(item, "text", "").lower() for item in result.feedback)


def test_interpretation_review_traces_capture_independent_contexts(tmp_path: Path) -> None:
    notebook = _notebook()
    notebook.cells.extend([
        nbformat.v4.new_markdown_cell(
            "Interpréter la première comparaison.",
            metadata={"tpstudio": {"role": "interpretation_prompt", "expectation_id": "interp-1"}},
        ),
        nbformat.v4.new_markdown_cell(
            "L'écart est faible, donc c'est bon.",
            metadata={"tpstudio": {"role": "interpretation_response", "expectation_id": "interp-1"}},
        ),
        nbformat.v4.new_markdown_cell(
            "Interpréter la seconde comparaison.",
            metadata={"tpstudio": {"role": "interpretation_prompt", "expectation_id": "interp-2"}},
        ),
        nbformat.v4.new_markdown_cell(
            "Le graphe est correct.",
            metadata={"tpstudio": {"role": "interpretation_response", "expectation_id": "interp-2"}},
        ),
    ])
    result = _analyze(tmp_path, notebook)
    traces = result.interpretation_review_traces
    assert [trace.expectation_id for trace in traces] == ["interp-1", "interp-2"]
    assert [trace.cell_index_snapshot for trace in traces] == [len(notebook.cells) - 3, len(notebook.cells) - 1]
    assert [trace.local_context.local_prompt for trace in traces] == [
        "Interpréter la première comparaison.",
        "Interpréter la seconde comparaison.",
    ]
    assert all(len(trace.copy_sha256) == 64 for trace in traces)
    assert traces[0].tpstudio_proposal is result.interpretation_response_evaluations[0].classification
    assert traces[1].tpstudio_proposal is result.interpretation_response_evaluations[1].classification
    assert "seconde" not in traces[0].local_context.reference_text
    assert "première" not in traces[1].local_context.reference_text


def test_missing_prepared_protocol_creates_one_targeted_feedback(tmp_path: Path) -> None:
    notebook = prepare_notebook_with_protocol_cells(_notebook(), snells_laws_manipulations())
    protocol_cells = [cell for cell in notebook.cells if cell.metadata.get("tpstudio", {}).get("role") == "protocol_response"]
    for cell in protocol_cells:
        cell.source += "\n\nNous plaçons le disque, alignons le rayon et relevons plusieurs angles dans un tableau."
    protocol_cells[1].source = "### Protocole expérimental\n\nVoir énoncé"
    result = _analyze(tmp_path, notebook)
    assert [item.status for item in result.protocol_evaluations].count(ProtocolStatus.MISSING) == 1
    protocol_feedback = [item for item in result.feedback if type(item).__name__ == "ProtocolFeedbackItem"]
    assert len(protocol_feedback) == 1
    protocol_annotations = [
        item for item in build_annotation_plan(result).annotations
        if any("PROTOCOL_EXPECTED_MISSING" in source_id for source_id in item.source_ids)
    ]
    assert len(protocol_annotations) == 1


def test_all_missing_protocol_cells_have_distinct_diagnostics(tmp_path: Path) -> None:
    notebook = prepare_notebook_with_protocol_cells(_notebook(), snells_laws_manipulations())
    result = _analyze(tmp_path, notebook)
    protocol_diagnostics = [
        item for item in result.diagnostics if type(item).__name__ == "ProtocolDiagnostic"
    ]
    assert len(protocol_diagnostics) == 3
    assert len({item.expectation_id for item in protocol_diagnostics}) == 3


def test_missing_response_is_annotated_on_section_anchor(tmp_path: Path) -> None:
    notebook = _notebook()
    notebook.cells.insert(0, nbformat.v4.new_markdown_cell("1. Mesure par angle limite\nConsigne professeur"))
    notebook = prepare_notebook_with_protocol_cells(notebook, snells_laws_manipulations())
    response_cells = [cell for cell in notebook.cells if cell.metadata.get("tpstudio", {}).get("role") == "protocol_response"]
    response_cells[0].metadata = {}
    response_cells[0].source = "texte historique sans réponse estampillée"
    for cell in response_cells[1:]:
        cell.source += "\n\nNous plaçons le disque, alignons le rayon et relevons plusieurs angles dans un tableau."
    result = _analyze(tmp_path, notebook)
    protocol_annotations = [
        item for item in build_annotation_plan(result).annotations
        if any("PROTOCOL_EXPECTED_MISSING" in source_id for source_id in item.source_ids)
    ]
    assert len(protocol_annotations) == 1
    assert protocol_annotations[0].target_cell_index == 0


def test_missing_response_without_section_is_not_placed_at_cell_zero(tmp_path: Path) -> None:
    notebook = prepare_notebook_with_protocol_cells(_notebook(), snells_laws_manipulations())
    for cell in notebook.cells:
        if cell.metadata.get("tpstudio", {}).get("role") in {"protocol_response", "protocol_prompt"}:
            cell.metadata = {}
            cell.source = "Texte sans section identifiée"
    result = _analyze(tmp_path, notebook)
    protocol_annotations = [
        item for item in build_annotation_plan(result).annotations
        if any("PROTOCOL_EXPECTED_MISSING" in source_id for source_id in item.source_ids)
    ]
    assert not protocol_annotations


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
