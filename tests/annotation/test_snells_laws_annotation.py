from pathlib import Path
import importlib.util
from dataclasses import replace

import nbformat

from tpstudio.annotation import AnnotationOptions, apply_annotation_plan, build_annotation_plan, find_tpstudio_annotations
from tpstudio.reporting import build_teacher_copy_report


def _module():
    path = Path("tests/orchestration/test_copy_analysis.py")
    spec = importlib.util.spec_from_file_location("annotation_integration_fixture", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_a71c_a71d_a71e_pipeline_is_read_only_and_idempotent(tmp_path) -> None:
    module = _module(); notebook = module._notebook(omit_marker="# Méthode statistique", placeholder=True)
    path = tmp_path / "source"; nbformat.write(notebook, path); before = path.read_bytes()
    result = module._analyze(tmp_path, notebook)
    report = build_teacher_copy_report(result)
    options = AnnotationOptions(include_teacher_feedback=True, include_diagnostics=True)
    plan = build_annotation_plan(result, report, options)
    first = apply_annotation_plan(notebook, plan, options)
    second = apply_annotation_plan(first.notebook, plan, options)
    assert first.notebook == second.notebook
    assert find_tpstudio_annotations(first.notebook)
    assert path.read_bytes() == before
    assert not hasattr(first, "score") and not hasattr(first, "grade")


def test_student_copy_never_includes_teacher_feedback(tmp_path) -> None:
    module = _module(); notebook = module._notebook(omit_marker="# Méthode statistique")
    result = module._analyze(tmp_path, notebook)
    plan = build_annotation_plan(result)
    assert not plan.teacher_annotations
    rendered = apply_annotation_plan(notebook, plan).notebook
    assert all(cell.get("metadata", {}).get("tpstudio", {}).get("audience") != "teacher" for cell in rendered.cells)


def test_real_comparison_feedbacks_keep_comparison_and_localize_to_distinct_text_cells(tmp_path) -> None:
    module = _module(); notebook = module._notebook()
    first = module._cell_with(
        notebook, "### Résultat — Seconde méthode de mesure de l'indice"
    )
    first.source = (
        "### Résultat — Seconde méthode de mesure de l'indice\n"
        "n = (1.52 ± 0.05)\nEn = 0,28"
    )
    second = module._cell_with(
        notebook, "### Comparaison des résultats obtenus"
    )
    second.source = "### Comparaison des résultats obtenus\nEn = 0,14"
    result = module._analyze(tmp_path, notebook)
    # This test exercises legacy comparison localization in isolation.  The
    # synthetic fixture has no actual ``### Réponse`` blocks, so its semantic
    # contracts otherwise (correctly) supersede the legacy comments as empty
    # responses.
    result = replace(result, semantic_response_analyses=())
    plan = build_annotation_plan(result)
    comparison_annotations = tuple(
        item for item in plan.annotations if item.comparison_id is not None
    )
    assert comparison_annotations
    comparison_ids = {item.comparison_id for item in comparison_annotations}
    assert comparison_ids <= {"compare_direct_geometric", "compare_geometric_regression"}
    expected_cells = {
        evaluation.comparison_id: evaluation.source_resolution.cell.index
        for evaluation in result.comparison_interpretation_evaluations
        if evaluation.source_resolution is not None
    }
    assert all(
        item.target_cell_index == expected_cells[item.comparison_id]
        for item in comparison_annotations
    )
    derived = apply_annotation_plan(notebook, plan).notebook
    assert len(find_tpstudio_annotations(derived)) >= len(comparison_annotations)
    assert len({expected_cells[item] for item in comparison_ids}) == 2
    left_quantity_cells = {
        result.production_resolutions.get(comparison.left_quantity_id).cell_index
        for comparison in result.quantity_comparison_evaluations
    }
    assert any(
        item.target_cell_index not in left_quantity_cells
        for item in comparison_annotations
    )
