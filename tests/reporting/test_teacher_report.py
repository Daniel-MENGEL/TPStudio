from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import importlib.util

import pytest

from tpstudio.reporting import TeacherCopyReport, build_teacher_copy_report


def _copy_test_module():
    path = Path("tests/orchestration/test_copy_analysis.py")
    spec = importlib.util.spec_from_file_location("copy_analysis_fixture", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_builder_projects_analysis_without_path_or_mutation(tmp_path) -> None:
    result = _copy_test_module()._analyze(tmp_path)
    report = build_teacher_copy_report(result)
    assert type(report) is TeacherCopyReport
    assert report.project_id == "snells-laws-mvp"
    assert report.source_id == "synthetic"
    assert len(report.productions) == 19
    assert str(tmp_path) not in repr(report)
    assert not hasattr(report, "score") and not hasattr(report, "grade")
    with pytest.raises(FrozenInstanceError): report.title = "x"


def test_overview_and_human_review_follow_analysis(tmp_path) -> None:
    module = _copy_test_module()
    result = module._analyze(tmp_path, module._notebook(placeholder=True, error=True))
    report = build_teacher_copy_report(result)
    assert report.overview.placeholder_count >= 1
    assert report.overview.technical_error_count == 1
    assert report.human_review.required
    assert report.priorities


def test_builder_rejects_non_analysis() -> None:
    with pytest.raises(TypeError): build_teacher_copy_report(object())


def test_quantity_counts_follow_scientific_assessment_not_value_presence(tmp_path) -> None:
    module = _copy_test_module()
    notebook = module._notebook()
    cell = module._cell_with(
        notebook, "### Résultat — Première méthode de mesure de l'indice"
    )
    cell.source = cell.source.replace("n = (1.50 ± 0.05)", "n = 1.50")
    result = module._analyze(tmp_path, notebook)
    report = build_teacher_copy_report(result)
    expected_evaluable = sum(
        item.assessed
        and item.assessment is not None
        and item.assessment.is_structurally_satisfied
        for item in result.quantity_evaluations
    )
    assert report.overview.evaluable_quantity_count == expected_evaluable
    assert report.overview.non_evaluable_quantity_count == len(report.quantities) - expected_evaluable
    non_evaluable_with_value = tuple(
        item for item in report.quantities if not item.evaluable and item.value is not None
    )
    assert non_evaluable_with_value
    assert all(item.value is not None for item in non_evaluable_with_value)
    assert any(item.evaluable and item.value is not None for item in report.quantities)


def test_external_path_strings_are_removed_from_teacher_model(tmp_path) -> None:
    result = _copy_test_module()._analyze(tmp_path)
    private_paths = (
        "/Users/example/private/data.csv",
        "/home/student/private/file.txt",
    )
    inspection = replace(
        result.technical_inspection,
        referenced_external_paths=private_paths,
    )
    report = build_teacher_copy_report(replace(result, technical_inspection=inspection))
    assert report.technical.external_path_reference_count == 2
    assert not hasattr(report.technical, "referenced_external_paths")
    assert all(path not in repr(report) for path in private_paths)


def test_feedback_and_diagnostic_source_keys_are_business_stable_not_positional(tmp_path) -> None:
    module = _copy_test_module()
    result = module._analyze(tmp_path, module._notebook(omit_marker="# Méthode statistique"))
    first = build_teacher_copy_report(result)
    reordered_result = replace(
        result,
        feedback=tuple(reversed(result.feedback)),
        diagnostics=tuple(reversed(result.diagnostics)),
    )
    second = build_teacher_copy_report(reordered_result)
    assert {item.source_key for item in first.feedback} == {item.source_key for item in second.feedback}
    assert {item.source_key for item in first.diagnostics} == {item.source_key for item in second.diagnostics}
    assert len({item.source_key for item in first.feedback}) == len(first.feedback)
    assert len({item.source_key for item in first.diagnostics}) == len(first.diagnostics)
    assert all(not item.source_key.startswith("feedback-00") for item in first.feedback)
    assert all(not item.source_key.startswith("diagnostic-00") for item in first.diagnostics)
