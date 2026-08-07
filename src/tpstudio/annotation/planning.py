"""Pure planning of localized annotations from A71c/A71d data."""

from __future__ import annotations

import hashlib

from tpstudio.feedback import FeedbackAudience
from tpstudio.orchestration import CopyAnalysisResult, ProductionResolutionStatus
from tpstudio.reporting import (
    TeacherCopyReport, TeacherReportSeverity, build_teacher_copy_report,
)

from .model import (
    AnnotationKind, AnnotationOptions, AnnotationPlacement, AnnotationPlan,
    NotebookAnnotation, SkippedAnnotation, SkippedAnnotationReason,
)


_SEVERITY_ORDER = {
    TeacherReportSeverity.BLOCKING: 0,
    TeacherReportSeverity.IMPORTANT: 1,
    TeacherReportSeverity.ATTENTION: 2,
    TeacherReportSeverity.INFO: 3,
}


def _stable_id(project_id: str, source_id: str, kind: AnnotationKind, audience: FeedbackAudience, source_key: str, target: int) -> str:
    canonical = "|".join((project_id, source_id, kind.value, audience.value, source_key, str(target), "v1"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]
    return f"tpstudio:{project_id}:{kind.value}:{digest}"


def _comparison_target(result: CopyAnalysisResult, comparison_id: str):
    if result.project.get_comparison(comparison_id) is None:
        return None, SkippedAnnotationReason.TARGET_UNAVAILABLE
    evaluations = (
        result.comparison_justification_evaluations.get(comparison_id),
        result.comparison_interpretation_evaluations.get(comparison_id),
        result.student_normalized_error_evaluations.get(comparison_id),
    )
    sources = tuple(
        evaluation.source_resolution
        for evaluation in evaluations
        if evaluation is not None and evaluation.source_resolution is not None
    )
    source_cells = {item.cell.index for item in sources if item.cell is not None}
    if len(source_cells) == 1:
        return sources[0], None
    if len(source_cells) > 1:
        return None, SkippedAnnotationReason.TARGET_AMBIGUOUS
    candidate_indices = {
        index
        for evaluation in evaluations
        if evaluation is not None
        for candidate in evaluation.source_candidates
        for index in candidate.candidate_indices
    }
    if len(candidate_indices) > 1:
        return None, SkippedAnnotationReason.TARGET_AMBIGUOUS
    return None, SkippedAnnotationReason.TARGET_UNAVAILABLE


def _target(result: CopyAnalysisResult, production_id: str | None, comparison_id: str | None):
    if production_id is None and comparison_id is not None:
        return _comparison_target(result, comparison_id)
    if production_id is None:
        return None, SkippedAnnotationReason.TARGET_UNAVAILABLE
    resolution = result.production_resolutions.get(production_id)
    if resolution is None or resolution.status is ProductionResolutionStatus.MISSING:
        return None, SkippedAnnotationReason.TARGET_UNAVAILABLE
    if resolution.status is ProductionResolutionStatus.AMBIGUOUS or resolution.cell_index is None:
        return None, SkippedAnnotationReason.TARGET_AMBIGUOUS
    return resolution.resolution, None


def _placement(cell_type: str, options: AnnotationOptions) -> AnnotationPlacement | None:
    if cell_type == "markdown":
        return AnnotationPlacement.APPEND_TO_MARKDOWN
    if options.annotate_code_by_adjacent_markdown:
        return AnnotationPlacement.AFTER_CELL
    return None


def _semantic_ids(result: CopyAnalysisResult, production_id, comparison_id):
    if comparison_id is None and production_id is not None and result.project.get_comparison(production_id) is not None:
        return None, production_id
    return production_id, comparison_id


def build_annotation_plan(
    result: CopyAnalysisResult,
    report: TeacherCopyReport | None = None,
    options: AnnotationOptions | None = None,
) -> AnnotationPlan:
    if type(result) is not CopyAnalysisResult:
        raise TypeError("Le plan exige exactement un CopyAnalysisResult.")
    options = AnnotationOptions() if options is None else options
    if type(options) is not AnnotationOptions:
        raise TypeError("Les options d'annotation sont invalides.")
    canonical_report = build_teacher_copy_report(result)
    report = canonical_report if report is None else report
    if type(report) is not TeacherCopyReport:
        raise TypeError("Le rapport est invalide.")
    if report != canonical_report:
        raise ValueError("Le rapport doit être la projection canonique de l'analyse.")
    annotations: list[NotebookAnnotation] = []
    skipped: list[SkippedAnnotation] = []

    for item in report.feedback:
        production_id, comparison_id = _semantic_ids(
            result, item.production_id, item.comparison_id
        )
        allowed = (
            item.audience is FeedbackAudience.STUDENT and options.include_student_feedback
        ) or (
            item.audience is FeedbackAudience.TEACHER and options.include_teacher_feedback
        )
        if not allowed:
            skipped.append(SkippedAnnotation(item.source_key, AnnotationKind.FEEDBACK, item.audience, SkippedAnnotationReason.AUDIENCE_EXCLUDED, production_id, comparison_id))
            continue
        resolution, reason = _target(result, production_id, comparison_id)
        if reason is not None:
            skipped.append(SkippedAnnotation(item.source_key, AnnotationKind.FEEDBACK, item.audience, reason, production_id, comparison_id))
            continue
        placement = _placement(resolution.cell.cell_type, options)
        if placement is None:
            skipped.append(SkippedAnnotation(item.source_key, AnnotationKind.FEEDBACK, item.audience, SkippedAnnotationReason.PLACEMENT_DISABLED, production_id, comparison_id))
            continue
        severity = {
            "high": TeacherReportSeverity.IMPORTANT,
            "normal": TeacherReportSeverity.ATTENTION,
            "low": TeacherReportSeverity.INFO,
        }.get(item.priority, TeacherReportSeverity.ATTENTION)
        annotation_id = _stable_id(result.project_id, result.source_id, AnnotationKind.FEEDBACK, item.audience, item.source_key, resolution.cell.index)
        annotations.append(NotebookAnnotation(
            annotation_id, AnnotationKind.FEEDBACK, item.audience, item.text,
            (item.source_key,), production_id, comparison_id,
            resolution.cell.index, placement, severity,
        ))

    if options.include_diagnostics:
        for item in report.diagnostics:
            production_id, comparison_id = _semantic_ids(
                result, item.production_id, item.comparison_id
            )
            audience = FeedbackAudience.TEACHER
            resolution, reason = _target(result, production_id, comparison_id)
            if reason is not None:
                skipped.append(SkippedAnnotation(item.source_key, AnnotationKind.DIAGNOSTIC, audience, reason, production_id, comparison_id))
                continue
            placement = _placement(resolution.cell.cell_type, options)
            if placement is None:
                skipped.append(SkippedAnnotation(item.source_key, AnnotationKind.DIAGNOSTIC, audience, SkippedAnnotationReason.PLACEMENT_DISABLED, production_id, comparison_id))
                continue
            annotation_id = _stable_id(result.project_id, result.source_id, AnnotationKind.DIAGNOSTIC, audience, item.source_key, resolution.cell.index)
            annotations.append(NotebookAnnotation(
                annotation_id, AnnotationKind.DIAGNOSTIC, audience, item.message_key,
                (item.source_key,), production_id, comparison_id,
                resolution.cell.index, placement, item.severity,
            ))

    if options.include_limitations:
        for index, _message in enumerate(report.limitations, 1):
            skipped.append(SkippedAnnotation(
                f"limitation-{index:03d}", AnnotationKind.LIMITATION,
                FeedbackAudience.TEACHER, SkippedAnnotationReason.TARGET_UNAVAILABLE,
            ))

    unique: dict[str, NotebookAnnotation] = {}
    for item in annotations:
        unique.setdefault(item.annotation_id, item)
    annotations = list(unique.values())
    annotations.sort(key=lambda item: (
        item.target_cell_index, _SEVERITY_ORDER[item.severity],
        item.kind.value, item.source_ids, item.annotation_id,
    ))
    return AnnotationPlan(
        result.project_id, result.source_id, tuple(annotations), tuple(skipped),
        tuple(result.limitations),
    )


def summarize_annotation_plan(plan: AnnotationPlan) -> str:
    if type(plan) is not AnnotationPlan:
        raise TypeError("Le résumé exige exactement un AnnotationPlan.")
    cells = tuple(dict.fromkeys(item.target_cell_index for item in plan.annotations))
    return "\n".join((
        f"Project: {plan.project_id}", f"Source: {plan.source_id}",
        f"Student annotations: {len(plan.student_annotations)}",
        f"Teacher annotations: {len(plan.teacher_annotations)}",
        f"Target cells: {list(cells)}", f"Skipped: {len(plan.skipped)}",
        f"Limitations: {len(plan.limitations)}",
    ))
