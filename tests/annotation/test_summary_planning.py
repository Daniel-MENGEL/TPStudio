from dataclasses import replace
import importlib.util
from pathlib import Path

import nbformat

from tpstudio.annotation import (
    AnnotationKind, AnnotationPlan, AnnotationPlacement, NotebookAnnotation,
    SkippedAnnotationReason, build_annotation_plan,
)
import tpstudio.annotation.planning as planning
from tpstudio.feedback import FeedbackAudience
from tpstudio.orchestration import ProductionResolutionStatus
from tpstudio.reporting import TeacherReportSeverity, build_teacher_copy_report
from tpstudio.reporting.teacher_report import TeacherFeedbackReportItem


def _fixture():
    spec = importlib.util.spec_from_file_location(
        "summary_copy_fixture", Path("tests/orchestration/test_copy_analysis.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _result(tmp_path):
    module = _fixture()
    return module._analyze(tmp_path)


def _plan_with_report(monkeypatch, result, report, *, reason=None):
    monkeypatch.setattr(planning, "build_teacher_copy_report", lambda _result: report)
    if reason is not None:
        monkeypatch.setattr(
            planning, "_target",
            lambda _result, _production_id, _comparison_id: (None, reason),
        )
    return build_annotation_plan(result)


def _feedback(production_id, *, audience=FeedbackAudience.STUDENT, priority="high", text="La production manque.", source="feedback:missing"):
    return TeacherFeedbackReportItem(
        f"id:{source}", source, audience, production_id, None, priority, text,
    )


def _production(report, production_id, *, required=True, status="missing", title="Production attendue"):
    original = next(item for item in report.productions if item.production_id == production_id)
    return replace(original, required=required, status=status, title=title)


def test_required_missing_without_feedback_becomes_summary(monkeypatch, tmp_path):
    result = _result(tmp_path)
    report = build_teacher_copy_report(result)
    production = _production(report, "direct_index", title="Indice par angle limite")
    report = replace(report, productions=tuple(
        production if item.production_id == production.production_id else item
        for item in report.productions
    ), feedback=())
    plan = _plan_with_report(monkeypatch, result, report)
    assert len(plan.summary_annotations) == 1
    assert plan.summary_annotations[0].audience is FeedbackAudience.STUDENT
    assert "Indice par angle limite" in plan.summary_annotations[0].message
    assert "n'a pas été retrouvée" in plan.summary_annotations[0].message
    assert not plan.skipped


def test_required_ambiguous_is_distinct_from_missing(monkeypatch, tmp_path):
    result = _result(tmp_path)
    report = build_teacher_copy_report(result)
    production = _production(report, "direct_index", status="ambiguous", title="Indice ambigu")
    report = replace(report, productions=tuple(
        production if item.production_id == production.production_id else item
        for item in report.productions
    ), feedback=())
    plan = _plan_with_report(monkeypatch, result, report)
    message = plan.summary_annotations[0].message
    assert "pourraient correspondre" in message
    assert "n'a pas été retrouvée" not in message
    assert "incorrecte" not in message


def test_optional_missing_is_not_promoted(monkeypatch, tmp_path):
    result = _result(tmp_path)
    report = build_teacher_copy_report(result)
    production = _production(report, "direct_index", required=False)
    report = replace(report, productions=tuple(
        production if item.production_id == production.production_id else item
        for item in report.productions
    ), feedback=())
    plan = _plan_with_report(monkeypatch, result, report)
    assert not plan.summary_annotations


def test_teacher_feedback_is_never_student_summary(monkeypatch, tmp_path):
    result = _result(tmp_path)
    report = build_teacher_copy_report(result)
    report = replace(report, feedback=(_feedback("direct_index", audience=FeedbackAudience.TEACHER),))
    plan = _plan_with_report(monkeypatch, result, report, reason=SkippedAnnotationReason.TARGET_UNAVAILABLE)
    assert not plan.summary_annotations


def test_important_untargeted_student_feedback_is_summary(monkeypatch, tmp_path):
    result = _result(tmp_path)
    report = build_teacher_copy_report(result)
    report = replace(report, feedback=(_feedback("direct_index", text="À revoir impérativement."),))
    plan = _plan_with_report(monkeypatch, result, report, reason=SkippedAnnotationReason.TARGET_UNAVAILABLE)
    assert len(plan.summary_annotations) == 1
    assert "À revoir impérativement" in plan.summary_annotations[0].message


def test_targeted_feedback_stays_local(monkeypatch, tmp_path):
    result = _result(tmp_path)
    report = build_teacher_copy_report(result)
    item = _feedback("direct_index")
    report = replace(report, feedback=(item,))
    plan = _plan_with_report(monkeypatch, result, report)
    assert len(plan.annotations) == 1
    assert not plan.summary_annotations


def test_attention_untargeted_non_required_is_not_promoted(monkeypatch, tmp_path):
    result = _result(tmp_path)
    report = build_teacher_copy_report(result)
    production = _production(report, "direct_index", required=False, status="resolved")
    item = _feedback("direct_index", priority="normal", text="Information secondaire.")
    report = replace(report, productions=tuple(
        production if x.production_id == production.production_id else x
        for x in report.productions
    ), feedback=(item,))
    plan = _plan_with_report(monkeypatch, result, report, reason=SkippedAnnotationReason.TARGET_UNAVAILABLE)
    assert not plan.summary_annotations


def test_identical_summary_feedback_is_deduplicated(monkeypatch, tmp_path):
    result = _result(tmp_path)
    report = build_teacher_copy_report(result)
    item = _feedback("direct_index")
    report = replace(report, feedback=(item, replace(item, feedback_id="id:duplicate")))
    plan = _plan_with_report(monkeypatch, result, report, reason=SkippedAnnotationReason.TARGET_UNAVAILABLE)
    assert len(plan.summary_annotations) == 1


def test_distinct_summary_feedbacks_are_kept(monkeypatch, tmp_path):
    result = _result(tmp_path)
    report = build_teacher_copy_report(result)
    first = _feedback("direct_index", text="Première remarque.", source="feedback:first")
    second = _feedback("direct_index", text="Deuxième remarque.", source="feedback:second")
    report = replace(report, feedback=(first, second))
    plan = _plan_with_report(monkeypatch, result, report, reason=SkippedAnnotationReason.TARGET_UNAVAILABLE)
    assert len(plan.summary_annotations) == 2


def test_missing_quantity_does_not_create_unit_uncertainty_triple(monkeypatch, tmp_path):
    result = _result(tmp_path)
    report = build_teacher_copy_report(result)
    items = (
        _feedback("direct_index", text="La grandeur attendue n'a pas été fournie.", source="feedback:value"),
        _feedback("direct_index", text="Précisez l'unité.", source="feedback:unit"),
        _feedback("direct_index", text="Précisez l'incertitude.", source="feedback:uncertainty"),
    )
    production = _production(report, "direct_index", status="missing")
    report = replace(report, productions=tuple(
        production if item.production_id == production.production_id else item
        for item in report.productions
    ), feedback=items)
    plan = _plan_with_report(monkeypatch, result, report, reason=SkippedAnnotationReason.TARGET_UNAVAILABLE)
    assert len(plan.summary_annotations) == 1
    assert "unité" not in plan.summary_annotations[0].message.lower()
    assert "incertitude" not in plan.summary_annotations[0].message.lower()


def test_missing_relation_uses_title_without_inventing_expression(monkeypatch, tmp_path):
    result = _result(tmp_path)
    report = build_teacher_copy_report(result)
    production = _production(report, "snell_relation", status="missing", title="Loi de Snell-Descartes")
    report = replace(report, productions=tuple(
        production if item.production_id == production.production_id else item
        for item in report.productions
    ), feedback=())
    plan = _plan_with_report(monkeypatch, result, report)
    message = plan.summary_annotations[0].message.lower()
    assert "loi de snell-descartes" in message
    assert "expression" not in message
    assert "incorrecte" not in message


def test_summary_and_skipped_are_disjoint_and_counted(monkeypatch, tmp_path):
    result = _result(tmp_path)
    report = build_teacher_copy_report(result)
    report = replace(report, feedback=(_feedback("direct_index"),))
    plan = _plan_with_report(monkeypatch, result, report, reason=SkippedAnnotationReason.TARGET_UNAVAILABLE)
    assert len(plan.summary_annotations) == 1
    assert not plan.skipped
    assert plan.count == len(plan.student_annotations) == 1
