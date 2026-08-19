from dataclasses import replace
from pathlib import Path

from tpstudio.reporting import build_teacher_copy_report
from tpstudio.web.execution import run_selected_dispatch
from tpstudio.web.model import TeacherScientificSeverity
from tpstudio.web.scientific_overview import (
    build_teacher_scientific_overview,
    scientific_detail_widget_key,
)

from .test_multi_project_analysis import _copies


def _reports(tmp_path):
    result = run_selected_dispatch(_copies(tmp_path))
    return tuple(build_teacher_copy_report(item.dispatch.analysis) for item in result.copies)


def test_overview_is_generic_and_keeps_only_report_families(tmp_path):
    snell, lens = _reports(tmp_path)
    snell_overview = build_teacher_scientific_overview(snell)
    lens_overview = build_teacher_scientific_overview(lens)
    assert [row.key for row in snell_overview.rows] == [
        "productions", "quantities", "comparisons", "relations", "conclusion", "limitations",
    ]
    assert [row.key for row in lens_overview.rows] == [
        "productions", "quantities", "comparisons", "relations", "conclusion", "limitations",
    ]
    assert all("snell" not in row.summary.lower() for row in snell_overview.rows)


def test_overview_marks_strong_comparison_as_error_without_scientific_recompute(tmp_path):
    report = _reports(tmp_path)[0]
    comparison = replace(report.comparisons[0], objective_status="strongly_incoherent")
    report = replace(report, comparisons=(comparison, *report.comparisons[1:]))
    row = next(item for item in build_teacher_scientific_overview(report).rows if item.key == "comparisons")
    assert row.severity is TeacherScientificSeverity.ERROR
    assert "incohérence forte" in row.summary
    assert "strongly_incoherent" in row.details[0]


def test_overview_distinguishes_non_evaluable_from_error(tmp_path):
    report = _reports(tmp_path)[0]
    row = next(item for item in build_teacher_scientific_overview(report).rows if item.key == "comparisons")
    assert row.severity is TeacherScientificSeverity.REVIEW
    assert "non évaluable" in row.summary
    assert "relation correcte" not in " ".join(item.summary for item in build_teacher_scientific_overview(report).rows).lower()


def test_overview_projects_unit_and_uncertainty_diagnostics(tmp_path):
    report = _reports(tmp_path)[0]
    diagnostic = replace(
        report.diagnostics[0],
        code="unit_mismatch",
        message_key="diagnostic.quantity.unit_mismatch",
    )
    report = replace(report, diagnostics=(diagnostic,))
    overview = build_teacher_scientific_overview(report)
    units = next(item for item in overview.rows if item.key == "units")
    assert units.severity is TeacherScientificSeverity.REVIEW
    assert "problème" in units.summary


def test_overview_projects_uncertainty_diagnostic_and_relation_presence(tmp_path):
    report = _reports(tmp_path)[0]
    diagnostic = replace(
        report.diagnostics[0],
        code="uncertainty_not_strictly_positive",
        message_key="diagnostic.quantity.uncertainty_not_strictly_positive",
    )
    report = replace(report, diagnostics=(diagnostic,))
    overview = build_teacher_scientific_overview(report)
    uncertainties = next(item for item in overview.rows if item.key == "uncertainties")
    relations = next(item for item in overview.rows if item.key == "relations")
    assert uncertainties.severity is TeacherScientificSeverity.REVIEW
    assert "problème" in uncertainties.summary
    assert "absente" in relations.summary
    assert "relation correcte" not in " ".join(item.summary for item in overview.rows).lower()


def test_deferred_uncertainty_is_not_reported_as_scientific_problem(tmp_path):
    report = _reports(tmp_path)[0]
    diagnostic = replace(
        report.diagnostics[0],
        code="uncertainty_justification_deferred",
        message_key="diagnostic.quantity.uncertainty_justification_deferred",
    )
    report = replace(report, diagnostics=(diagnostic,))
    row = next(item for item in build_teacher_scientific_overview(report).rows if item.key == "uncertainties")
    assert row.summary == "contrôle différé"
    assert "1 problème" not in row.summary


def test_unrelated_quantity_priority_does_not_contaminate_units_or_uncertainties(tmp_path):
    report = _reports(tmp_path)[0]
    diagnostic = replace(
        report.diagnostics[0],
        diagnostic_id="diagnostic-unit",
        code="unit_missing",
        message_key="diagnostic.quantity.unit_missing",
    )
    priority = replace(
        report.priorities[0],
        category=type(report.priorities[0].category).QUANTITY,
        severity=type(report.priorities[0].severity).BLOCKING,
        diagnostic_ids=(),
    )
    report = replace(report, diagnostics=(diagnostic,), priorities=(priority,))
    overview = build_teacher_scientific_overview(report)
    units = next(row for row in overview.rows if row.key == "units")
    assert units.severity.value == "review"


def test_detail_widget_keys_are_unique_per_copy_and_row():
    assert scientific_detail_widget_key("copy-001", "units") != scientific_detail_widget_key("copy-002", "units")
    assert scientific_detail_widget_key("copy-001", "units") != scientific_detail_widget_key("copy-001", "comparisons")


def test_overview_conclusion_and_limitations_are_presentation_only(tmp_path):
    report = _reports(tmp_path)[1]
    overview = build_teacher_scientific_overview(report)
    conclusion = next(item for item in overview.rows if item.key == "conclusion")
    limitations = next(item for item in overview.rows if item.key == "limitations")
    assert conclusion.summary in {"présente", "absente"}
    assert limitations.severity is TeacherScientificSeverity.INFO
    text = " ".join(item.summary for item in overview.rows).lower()
    assert "production validée" not in text


def test_overview_hides_irrelevant_families(tmp_path):
    report = _reports(tmp_path)[1]
    report = replace(report, limitations=())
    keys = {row.key for row in build_teacher_scientific_overview(report).rows}
    assert "uncertainties" not in keys
    assert "limitations" not in keys
