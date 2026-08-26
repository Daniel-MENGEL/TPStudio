from dataclasses import replace
from pathlib import Path
import importlib.util

import pytest

from tpstudio.annotation import (
    AnnotationKind, AnnotationOptions, build_annotation_plan,
    summarize_annotation_plan,
)
from tpstudio.feedback import FeedbackAudience
from tpstudio.reporting import TeacherReportSeverity, build_teacher_copy_report
from tpstudio.annotation.model import SkippedAnnotationReason
from tpstudio.annotation.planning import _placement
from tpstudio.annotation.planning import (
    _comparison_target, _feedback_severity, _semantic_annotation_message,
    _stable_id, _target,
)
from tpstudio.semantic_analysis import (
    ExpectedSemanticResponse,
    SemanticAnalysisResult,
    SemanticCriterion,
    SemanticCriterionImportance,
    SemanticCriterionResult,
    SemanticCriterionStatus,
    SemanticRole,
)


def _module():
    path = Path("tests/orchestration/test_copy_analysis.py")
    spec = importlib.util.spec_from_file_location("annotation_plan_fixture", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_default_plan_uses_only_existing_student_feedback(tmp_path) -> None:
    module = _module(); result = module._analyze(tmp_path, module._notebook(omit_marker="# Méthode statistique"))
    plan = build_annotation_plan(result)
    assert all(item.audience is FeedbackAudience.STUDENT for item in plan.annotations)
    assert all(item.kind is AnnotationKind.FEEDBACK for item in plan.annotations)
    texts = {item.text for item in result.feedback if item.audience is FeedbackAudience.STUDENT}
    assert all(item.message in texts for item in plan.annotations)


def test_low_priority_corrective_feedback_is_attention_not_positive_info() -> None:
    assert _feedback_severity("low") is TeacherReportSeverity.ATTENTION


def test_missing_quantity_feedback_is_blocking_red_severity() -> None:
    assert _feedback_severity(
        "high",
        "feedback:QuantityFeedbackItem:quantity_missing:student:value:-:-:-",
    ) is TeacherReportSeverity.BLOCKING


def test_recommended_semantic_improvement_is_attention_not_positive_info() -> None:
    contract = ExpectedSemanticResponse(
        "interpretation",
        SemanticRole.INTERPRETATION,
        (
            SemanticCriterion(
                "required",
                "Élément requis",
                SemanticCriterionImportance.REQUIRED,
            ),
            SemanticCriterion(
                "recommended",
                "Élément recommandé",
                SemanticCriterionImportance.RECOMMENDED,
            ),
        ),
    )
    result = SemanticAnalysisResult(
        "interpretation",
        "Réponse étudiante.",
        (
            SemanticCriterionResult(
                "required", SemanticCriterionStatus.SATISFIED, "Présent."
            ),
            SemanticCriterionResult(
                "recommended", SemanticCriterionStatus.NOT_FOUND, ""
            ),
        ),
    )

    message, severity = _semantic_annotation_message(
        type("Analysis", (), {"contract": contract, "result": result})()
    )

    assert "Piste d'amélioration" in message
    assert severity is TeacherReportSeverity.ATTENTION


def test_teacher_and_diagnostics_require_explicit_options(tmp_path) -> None:
    module = _module(); result = module._analyze(tmp_path, module._notebook(omit_marker="# Méthode statistique"))
    report = build_teacher_copy_report(result)
    default = build_annotation_plan(result, report)
    explicit = build_annotation_plan(result, report, AnnotationOptions(include_teacher_feedback=True, include_diagnostics=True))
    assert not default.teacher_annotations
    assert explicit.teacher_annotations
    assert any(item.kind is AnnotationKind.DIAGNOSTIC for item in explicit.annotations)


def test_targets_placements_order_and_summary_are_deterministic(tmp_path) -> None:
    module = _module(); result = module._analyze(tmp_path, module._notebook(omit_marker="# Méthode statistique"))
    first = build_annotation_plan(result); second = build_annotation_plan(result)
    assert first == second
    severity_order = {
        TeacherReportSeverity.BLOCKING: 0,
        TeacherReportSeverity.IMPORTANT: 1,
        TeacherReportSeverity.ATTENTION: 2,
        TeacherReportSeverity.INFO: 3,
    }
    keys = tuple(
        (
            item.target_cell_index,
            severity_order[item.severity],
            item.kind.value,
            item.source_ids,
            item.annotation_id,
        )
        for item in first.annotations
    )
    assert keys == tuple(sorted(keys))
    summary = summarize_annotation_plan(first)
    assert "Project: snells-laws-mvp" in summary and str(tmp_path) not in summary


def test_missing_target_is_skipped_not_arbitrarily_selected(tmp_path) -> None:
    module = _module(); result = module._analyze(tmp_path, module._notebook(omit_marker="# Méthode statistique"))
    plan = build_annotation_plan(result, options=AnnotationOptions(include_teacher_feedback=True, include_diagnostics=True, include_limitations=True))
    assert plan.has_skipped
    assert all(item.reason.value in {"target_unavailable", "target_ambiguous", "audience_excluded"} for item in plan.skipped)


def test_comparison_ids_resolve_through_their_configured_text_sources(tmp_path) -> None:
    module = _module(); result = module._analyze(tmp_path)
    first, first_reason = _comparison_target(result, "compare_direct_geometric")
    second, second_reason = _comparison_target(result, "compare_geometric_regression")
    assert first_reason is second_reason is None
    assert first.cell.index != second.cell.index
    assert _stable_id(
        result.project_id, result.source_id, AnnotationKind.FEEDBACK,
        FeedbackAudience.STUDENT, "feedback:comparison:direct", first.cell.index,
    ) == _stable_id(
        result.project_id, result.source_id, AnnotationKind.FEEDBACK,
        FeedbackAudience.STUDENT, "feedback:comparison:direct", first.cell.index,
    )


def test_unknown_or_ambiguous_comparison_is_skipped(tmp_path) -> None:
    module = _module(); result = module._analyze(tmp_path)
    unknown, reason = _comparison_target(result, "unknown-comparison")
    assert unknown is None and reason is SkippedAnnotationReason.TARGET_UNAVAILABLE
    ambiguous_result = module._analyze(
        tmp_path, module._notebook(duplicate_marker="### Résultat — Seconde méthode de mesure de l'indice")
    )
    ambiguous, reason = _comparison_target(ambiguous_result, "compare_direct_geometric")
    assert ambiguous is None and reason is SkippedAnnotationReason.TARGET_AMBIGUOUS


def test_code_placement_option_is_effective_while_markdown_remains_allowed(tmp_path) -> None:
    module = _module(); result = module._analyze(tmp_path)
    code, reason = _target(result, "critical_angle", None)
    markdown, markdown_reason = _target(result, "direct_index", None)
    assert reason is markdown_reason is None
    assert _placement(code.cell.cell_type, AnnotationOptions()).value == "after_cell"
    assert _placement(code.cell.cell_type, AnnotationOptions(annotate_code_by_adjacent_markdown=False)) is None
    assert _placement(markdown.cell.cell_type, AnnotationOptions(annotate_code_by_adjacent_markdown=False)).value == "append_to_markdown"
    assert _placement("raw", AnnotationOptions(annotate_code_by_adjacent_markdown=False)) is None


@pytest.mark.parametrize("mutation", ("text", "source_key", "production_id", "comparison_id", "extra"))
def test_modified_report_cannot_inject_feedback(tmp_path, mutation) -> None:
    module = _module(); result = module._analyze(tmp_path, module._notebook(omit_marker="# Méthode statistique"))
    report = build_teacher_copy_report(result)
    item = report.feedback[0]
    if mutation == "extra":
        feedback = report.feedback + (item,)
    else:
        values = {
            "text": {"text": item.text + " inventé"},
            "source_key": {"source_key": item.source_key + ":fake"},
            "production_id": {"production_id": "final_conclusion"},
            "comparison_id": {"comparison_id": "compare_direct_geometric"},
        }[mutation]
        feedback = (replace(item, **values),) + report.feedback[1:]
    with pytest.raises(ValueError, match="canonique"):
        build_annotation_plan(result, replace(report, feedback=feedback))


def test_modified_diagnostic_is_rejected_and_canonical_report_is_accepted(tmp_path) -> None:
    module = _module(); result = module._analyze(tmp_path, module._notebook(omit_marker="# Méthode statistique"))
    report = build_teacher_copy_report(result)
    assert build_annotation_plan(result, report) == build_annotation_plan(result)
    diagnostic = report.diagnostics[0]
    fake = replace(report, diagnostics=(replace(diagnostic, source_key=diagnostic.source_key + ":fake"),) + report.diagnostics[1:])
    with pytest.raises(ValueError, match="canonique"):
        build_annotation_plan(result, fake)
