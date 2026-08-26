from pathlib import Path
import importlib.util

from tpstudio.reporting import build_teacher_copy_report, render_teacher_report_markdown


def _module():
    path = Path("tests/orchestration/test_copy_analysis.py")
    spec = importlib.util.spec_from_file_location("copy_reporting_fixture", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_favorable_synthetic_copy_has_complete_structured_report(tmp_path) -> None:
    module = _module(); report = build_teacher_copy_report(module._analyze(tmp_path))
    assert len(report.productions) == 24 and len(report.comparisons) == 2
    assert report.final_conclusion.production_id == "final_conclusion"
    assert report.comparisons[-1].comparison_id != report.final_conclusion.production_id


def test_missing_production_and_placeholder_are_visible(tmp_path) -> None:
    module = _module()
    result = module._analyze(tmp_path, module._notebook(placeholder=True, omit_marker="# Méthode statistique"))
    report = build_teacher_copy_report(result)
    assert any(item.status == "missing" for item in report.productions)
    assert any(item.title == "Code à compléter" for item in report.priorities)
    assert report.human_review.required


def test_saved_error_and_inverted_graph_remain_separate(tmp_path) -> None:
    module = _module()
    report = build_teacher_copy_report(module._analyze(tmp_path, module._notebook(error=True, inverted_graph=True)))
    assert report.overview.technical_error_count == 1
    assert report.overview.graph_issue_count >= 1
    assert len(report.comparisons) == 2


def test_report_does_not_choose_ambiguous_value_or_leak_path(tmp_path) -> None:
    module = _module(); result = module._analyze(tmp_path)
    report = build_teacher_copy_report(result)
    text = render_teacher_report_markdown(report)
    assert str(tmp_path) not in text and "@" not in text
    assert all(item.value is None for item in report.values if item.status == "ambiguous")


def test_two_builds_and_renders_are_identical(tmp_path) -> None:
    module = _module(); result = module._analyze(tmp_path)
    assert render_teacher_report_markdown(build_teacher_copy_report(result)) == render_teacher_report_markdown(build_teacher_copy_report(result))
