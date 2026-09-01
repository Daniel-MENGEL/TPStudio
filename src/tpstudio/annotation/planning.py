"""Pure planning of localized annotations from A71c/A71d data."""

from __future__ import annotations

from dataclasses import replace
import hashlib

from tpstudio.feedback import FeedbackAudience
from tpstudio.orchestration import CopyAnalysisResult, ProductionResolutionStatus
from tpstudio.reporting import (
    TeacherCopyReport, TeacherReportSeverity, build_teacher_copy_report,
)
from tpstudio.semantic_analysis import (
    SemanticCriterionImportance,
    SemanticCriterionStatus,
    SemanticRole,
)

from .model import (
    AnnotationKind, AnnotationOptions, AnnotationPlacement, AnnotationPlan,
    AnnotationReview, AnnotationReviewAction, AnnotationReviewLevel,
    NotebookAnnotation, SkippedAnnotation, SkippedAnnotationReason,
    StudentSummaryAnnotation,
)


def apply_annotation_reviews(
    plan: AnnotationPlan,
    reviews: tuple[AnnotationReview, ...] = (),
) -> AnnotationPlan:
    """Return the reviewed plan without mutating the automatic proposal."""

    if type(plan) is not AnnotationPlan:
        raise TypeError("Le plan de revue est invalide.")
    reviews = tuple(reviews)
    if any(type(item) is not AnnotationReview for item in reviews):
        raise TypeError("Une décision de revue est invalide.")
    review_by_id = {item.annotation_id: item for item in reviews}
    if len(review_by_id) != len(reviews):
        raise ValueError("Une annotation ne peut recevoir qu'une décision.")
    known_ids = {
        item.annotation_id for item in plan.annotations + plan.summary_annotations
    }
    unknown = set(review_by_id) - known_ids
    if unknown:
        raise ValueError("Une décision cible une annotation inconnue.")

    def reviewed(items):
        result = []
        for item in items:
            decision = review_by_id.get(item.annotation_id)
            if decision is None:
                result.append(item)
            elif decision.action is AnnotationReviewAction.KEEP:
                result.append(_apply_review_level(item, decision.level))
            elif decision.action is AnnotationReviewAction.EDIT:
                result.append(_apply_review_level(
                    replace(item, message=decision.message), decision.level
                ))
        return tuple(result)

    return replace(
        plan,
        annotations=reviewed(plan.annotations),
        summary_annotations=reviewed(plan.summary_annotations),
    )


_REVIEW_LEVEL_SEVERITY = {
    AnnotationReviewLevel.ABSENT: TeacherReportSeverity.BLOCKING,
    AnnotationReviewLevel.TO_REVIEW: TeacherReportSeverity.IMPORTANT,
    AnnotationReviewLevel.PARTIAL: TeacherReportSeverity.ATTENTION,
    AnnotationReviewLevel.GOOD: TeacherReportSeverity.INFO,
    AnnotationReviewLevel.VERY_GOOD: TeacherReportSeverity.INFO,
}


def _apply_review_level(item, level: AnnotationReviewLevel | None):
    if level is None:
        return item
    metadata = tuple(
        pair for pair in item.metadata if pair[0] != "review_level"
    ) + (("review_level", level.value),)
    return replace(item, severity=_REVIEW_LEVEL_SEVERITY[level], metadata=metadata)


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


def _feedback_severity(
    priority: str,
    source_key: str = "",
) -> TeacherReportSeverity:
    if ":quantity_missing:" in source_key:
        return TeacherReportSeverity.BLOCKING
    priority = getattr(priority, "value", priority)
    return {
        "high": TeacherReportSeverity.IMPORTANT,
        "normal": TeacherReportSeverity.ATTENTION,
        # A low-priority corrective remark is still something to check. INFO
        # is reserved for genuinely positive or neutral information.
        "low": TeacherReportSeverity.ATTENTION,
    }.get(str(priority).lower(), TeacherReportSeverity.ATTENTION)


def _summary_message(item, production, reason: SkippedAnnotationReason) -> str:
    title = production.title if production is not None else None
    if reason is SkippedAnnotationReason.TARGET_AMBIGUOUS:
        suffix = (
            "plusieurs éléments pourraient correspondre à cette production ; "
            "la réponse n'a pas pu être identifiée de façon fiable."
        )
    else:
        suffix = item.text
    return f"{title} — {suffix}" if title else item.text


def _summary_candidate(item, production, reason: SkippedAnnotationReason):
    if item.audience is not FeedbackAudience.STUDENT:
        return False
    required_missing = production is not None and production.required and production.status.lower() == "missing"
    required_ambiguous = production is not None and production.required and production.status.lower() == "ambiguous"
    important = getattr(item.priority, "value", item.priority) == "high"
    return required_missing or required_ambiguous or important


def _production_summary_severity(report: TeacherCopyReport, production_id: str) -> TeacherReportSeverity:
    priorities = tuple(item for item in report.priorities if item.production_id == production_id)
    return priorities[0].severity if priorities else TeacherReportSeverity.ATTENTION


def _semantic_annotation_message(analysis) -> tuple[str, TeacherReportSeverity]:
    """Render a concise student-facing projection of one semantic result."""

    result = analysis.result
    contract = analysis.contract
    assert result is not None
    statuses = {item.criterion_id: item.status for item in result.criterion_results}
    satisfied = [
        item.description for item in contract.criteria
        if statuses.get(item.criterion_id) is SemanticCriterionStatus.SATISFIED
    ]
    required_to_improve = [
        item.description for item in contract.criteria
        if item.importance is SemanticCriterionImportance.REQUIRED
        and statuses.get(item.criterion_id) in {
            SemanticCriterionStatus.PARTIAL,
            SemanticCriterionStatus.NOT_FOUND,
            SemanticCriterionStatus.UNCERTAIN,
        }
    ]
    recommended_to_improve = [
        item.description for item in contract.criteria
        if item.importance is SemanticCriterionImportance.RECOMMENDED
        and statuses.get(item.criterion_id) in {
            SemanticCriterionStatus.PARTIAL,
            SemanticCriterionStatus.NOT_FOUND,
            SemanticCriterionStatus.UNCERTAIN,
        }
    ]
    parts = ["Analyse sémantique assistée de cette réponse."]
    if satisfied:
        parts.append("Points repérés : " + " ; ".join(satisfied) + ".")
    if required_to_improve:
        parts.append("À compléter ou préciser : " + " ; ".join(required_to_improve) + ".")
    if recommended_to_improve:
        parts.append("Piste d'amélioration : " + " ; ".join(recommended_to_improve) + ".")
    if result.contradictions:
        parts.append(
            "Contradictions à examiner : " + " ; ".join(result.contradictions) + "."
        )
    if not (satisfied or required_to_improve or recommended_to_improve or result.contradictions):
        parts.append("Aucun élément suffisamment fiable n'a pu être dégagé.")
    severity = (
        TeacherReportSeverity.IMPORTANT
        if result.contradictions
        else TeacherReportSeverity.ATTENTION
        if required_to_improve or recommended_to_improve
        else TeacherReportSeverity.INFO
    )
    return "\n\n".join(parts), severity


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
    summary_annotations: list[StudentSummaryAnnotation] = []
    skipped: list[SkippedAnnotation] = []
    productions = {item.production_id: item for item in report.productions}
    summary_keys: set[tuple] = set()
    summarized_productions: set[str] = set()

    # When an actual semantic result exists, it is the authoritative
    # student-facing assessment of the corresponding free response.  Keep the
    # legacy phrase-based evaluations in the analysis/report for auditability,
    # but do not render a second, potentially contradictory comment beside the
    # same answer.
    semantic_cells: set[int] = set()
    semantic_protocol_cells: set[int] = set()
    for semantic_analysis in result.semantic_response_analyses:
        semantic_result = semantic_analysis.result
        resolution = semantic_analysis.resolution
        if semantic_result is None or resolution is None or resolution.cell is None:
            continue
        if semantic_result.diagnostics and "EMPTY_RESPONSE" not in semantic_result.diagnostics:
            continue
        semantic_cells.add(resolution.cell.index)
        if semantic_analysis.contract.semantic_role is SemanticRole.PROTOCOL:
            semantic_protocol_cells.add(resolution.cell.index)

    for item in report.feedback:
        production_id, comparison_id = _semantic_ids(result, item.production_id, item.comparison_id)
        allowed = (
            item.audience is FeedbackAudience.STUDENT and options.include_student_feedback
        ) or (
            item.audience is FeedbackAudience.TEACHER and options.include_teacher_feedback
        )
        if not allowed:
            skipped.append(SkippedAnnotation(item.source_key, AnnotationKind.FEEDBACK, item.audience, SkippedAnnotationReason.AUDIENCE_EXCLUDED, production_id, comparison_id))
            continue

        if item.audience is FeedbackAudience.STUDENT:
            legacy_narrative = any(
                name in item.source_key
                for name in (
                    "ComparisonInterpretationFeedbackItem",
                    "ComparisonJustificationFeedbackItem",
                )
            )
            if legacy_narrative:
                semantic_target, semantic_target_reason = _target(
                    result, production_id, comparison_id
                )
                if (
                    semantic_target_reason is None
                    and semantic_target is not None
                    and semantic_target.cell is not None
                    and semantic_target.cell.index in semantic_cells
                ):
                    skipped.append(SkippedAnnotation(
                        item.source_key,
                        AnnotationKind.FEEDBACK,
                        item.audience,
                        SkippedAnnotationReason.DUPLICATE,
                        production_id,
                        comparison_id,
                    ))
                    continue
            if (
                "ProtocolFeedbackItem" in item.source_key
                and item.cell_index is not None
                and any(
                    abs(item.cell_index - cell_index) <= 1
                    for cell_index in semantic_protocol_cells
                )
            ):
                skipped.append(SkippedAnnotation(
                    item.source_key,
                    AnnotationKind.FEEDBACK,
                    item.audience,
                    SkippedAnnotationReason.DUPLICATE,
                    production_id,
                    comparison_id,
                ))
                continue

        if item.cell_index is not None and production_id is None and comparison_id is None:
            if item.cell_index < 0 or item.cell_index >= result.technical_inspection.cell_count:
                reason = SkippedAnnotationReason.TARGET_UNAVAILABLE
                production = None
            else:
                placement = _placement(item.cell_type or "markdown", options)
                if placement is None:
                    skipped.append(SkippedAnnotation(item.source_key, AnnotationKind.FEEDBACK, item.audience, SkippedAnnotationReason.PLACEMENT_DISABLED))
                    continue
                annotation_id = _stable_id(result.project_id, result.source_id, AnnotationKind.FEEDBACK, item.audience, item.source_key, item.cell_index)
                annotations.append(NotebookAnnotation(
                    annotation_id, AnnotationKind.FEEDBACK, item.audience, item.text,
                    (item.source_key,), None, None,
                    item.cell_index, placement,
                    _feedback_severity(item.priority, item.source_key),
                ))
                continue
        else:
            resolution, reason = _target(result, production_id, comparison_id)
            production = productions.get(production_id)

        if reason is not None:
            if _summary_candidate(item, production, reason):
                if production_id is not None and production_id in summarized_productions:
                    continue
                key = (production_id, comparison_id, item.audience, item.source_key, reason, item.text)
                if key not in summary_keys:
                    summary_keys.add(key)
                    summary_annotations.append(StudentSummaryAnnotation(
                        annotation_id=f"tpstudio:student-summary:{len(summary_annotations):04d}",
                        audience=item.audience,
                        message=_summary_message(item, production, reason),
                        severity=_feedback_severity(item.priority, item.source_key),
                        reason=reason,
                        production_id=production_id,
                        comparison_id=comparison_id,
                        source_ids=(item.source_key,),
                    ))
                    if production_id is not None and production is not None and production.status.lower() in {"missing", "ambiguous"}:
                        summarized_productions.add(production_id)
                continue
            skipped.append(SkippedAnnotation(item.source_key, AnnotationKind.FEEDBACK, item.audience, reason, production_id, comparison_id))
            continue
        placement = _placement(resolution.cell.cell_type, options)
        if placement is None:
            skipped.append(SkippedAnnotation(item.source_key, AnnotationKind.FEEDBACK, item.audience, SkippedAnnotationReason.PLACEMENT_DISABLED, production_id, comparison_id))
            continue
        annotation_id = _stable_id(result.project_id, result.source_id, AnnotationKind.FEEDBACK, item.audience, item.source_key, resolution.cell.index)
        annotations.append(NotebookAnnotation(
            annotation_id, AnnotationKind.FEEDBACK, item.audience, item.text,
            (item.source_key,), production_id, comparison_id,
            resolution.cell.index, placement,
            _feedback_severity(item.priority, item.source_key),
        ))

    # Some mandatory productions have a report status but no separate student
    # feedback item (for example a missing value). Preserve that existing status
    # in the student summary without consulting the project or analysis engine.
    for production in report.productions:
        status = production.status.lower()
        if not production.required or status not in {"missing", "ambiguous"}:
            continue
        if production.production_id in summarized_productions:
            continue
        reason = (
            SkippedAnnotationReason.TARGET_AMBIGUOUS
            if status == "ambiguous" else SkippedAnnotationReason.TARGET_UNAVAILABLE
        )
        message = (
            f"{production.title} — plusieurs éléments pourraient correspondre à cette production ; "
            "la réponse n'a pas pu être identifiée de façon fiable."
            if status == "ambiguous" else
            f"{production.title} — cette production attendue n'a pas été retrouvée."
        )
        summary_annotations.append(StudentSummaryAnnotation(
            annotation_id=f"tpstudio:student-summary:{len(summary_annotations):04d}",
            audience=FeedbackAudience.STUDENT,
            message=message,
            severity=_production_summary_severity(report, production.production_id),
            reason=reason,
            production_id=production.production_id,
            source_ids=(f"production:{production.production_id}",),
        ))
        summarized_productions.add(production.production_id)

    # Semantic analyses are auditable analysis results rather than legacy
    # feedback catalog items. Project them locally only when an actual provider
    # result exists; empty responses and technical provider diagnostics never
    # become student comments.
    for semantic_analysis in result.semantic_response_analyses:
        semantic_result = semantic_analysis.result
        if semantic_result is None:
            continue
        empty_response = "EMPTY_RESPONSE" in semantic_result.diagnostics
        if semantic_result.diagnostics and not empty_response:
            continue
        source_key = f"semantic:{semantic_analysis.contract.production_id}"
        if not options.include_student_feedback:
            skipped.append(SkippedAnnotation(
                source_key,
                AnnotationKind.FEEDBACK,
                FeedbackAudience.STUDENT,
                SkippedAnnotationReason.AUDIENCE_EXCLUDED,
                semantic_analysis.contract.production_id,
            ))
            continue
        resolution = semantic_analysis.resolution
        if resolution is None or resolution.cell is None:
            skipped.append(SkippedAnnotation(
                source_key,
                AnnotationKind.FEEDBACK,
                FeedbackAudience.STUDENT,
                SkippedAnnotationReason.TARGET_UNAVAILABLE,
                semantic_analysis.contract.production_id,
            ))
            continue
        placement = _placement(resolution.cell.cell_type, options)
        if placement is None:
            skipped.append(SkippedAnnotation(
                source_key,
                AnnotationKind.FEEDBACK,
                FeedbackAudience.STUDENT,
                SkippedAnnotationReason.PLACEMENT_DISABLED,
                semantic_analysis.contract.production_id,
            ))
            continue
        if empty_response:
            message = "La réponse attendue n’a pas été fournie."
            severity = TeacherReportSeverity.BLOCKING
        else:
            message, severity = _semantic_annotation_message(semantic_analysis)
        metadata = (("origin", "semantic_analysis"), *semantic_result.provider_metadata)
        annotation_id = _stable_id(
            result.project_id,
            result.source_id,
            AnnotationKind.FEEDBACK,
            FeedbackAudience.STUDENT,
            source_key,
            resolution.cell.index,
        )
        annotations.append(NotebookAnnotation(
            annotation_id,
            AnnotationKind.FEEDBACK,
            FeedbackAudience.STUDENT,
            message,
            (source_key,),
            semantic_analysis.contract.production_id,
            None,
            resolution.cell.index,
            placement,
            severity,
            metadata,
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
    # Two productions can share one result cell. Merge identical localized
    # messages instead of displaying the same corrective block twice.
    consolidated: dict[tuple, NotebookAnnotation] = {}
    for item in annotations:
        key = (
            item.target_cell_index,
            item.kind,
            item.audience,
            item.message,
            item.placement,
            item.severity,
            item.metadata,
        )
        previous = consolidated.get(key)
        if previous is None:
            consolidated[key] = item
            continue
        consolidated[key] = replace(
            previous,
            source_ids=tuple(dict.fromkeys((*previous.source_ids, *item.source_ids))),
            production_id=(
                previous.production_id
                if previous.production_id == item.production_id else None
            ),
            comparison_id=(
                previous.comparison_id
                if previous.comparison_id == item.comparison_id else None
            ),
        )
    annotations = list(consolidated.values())
    annotations.sort(key=lambda item: (
        item.target_cell_index, _SEVERITY_ORDER[item.severity],
        item.kind.value, item.source_ids, item.annotation_id,
    ))
    return AnnotationPlan(
        result.project_id, result.source_id, tuple(annotations), tuple(skipped),
        tuple(result.limitations), tuple(summary_annotations),
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
