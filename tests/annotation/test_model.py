from dataclasses import FrozenInstanceError

import pytest

from tpstudio.annotation import (
    AnnotationKind, AnnotationOptions, AnnotationPlacement, AnnotationPlan,
    AnnotationReview, AnnotationReviewAction, AnnotationReviewLevel,
    apply_annotation_reviews,
    NotebookAnnotation,
)


def test_annotation_reviews_keep_edit_and_remove_without_mutating_plan():
    first = NotebookAnnotation(
        "first", AnnotationKind.FEEDBACK, FeedbackAudience.STUDENT,
        "Automatique", ("source-first",), None, None, 0,
        AnnotationPlacement.APPEND_TO_MARKDOWN, TeacherReportSeverity.ATTENTION,
    )
    second = NotebookAnnotation(
        "second", AnnotationKind.FEEDBACK, FeedbackAudience.STUDENT,
        "À retirer", ("source-second",), None, None, 0,
        AnnotationPlacement.APPEND_TO_MARKDOWN, TeacherReportSeverity.ATTENTION,
    )
    plan = AnnotationPlan("project", "source", (first, second))

    reviewed = apply_annotation_reviews(plan, (
        AnnotationReview("first", AnnotationReviewAction.EDIT, "Validé et précisé."),
        AnnotationReview("second", AnnotationReviewAction.REMOVE),
    ))

    assert tuple(item.annotation_id for item in reviewed.annotations) == ("first",)
    assert reviewed.annotations[0].message == "Validé et précisé."
    assert plan.annotations == (first, second)


def test_annotation_review_rejects_unknown_annotation():
    plan = AnnotationPlan("project", "source", ())
    with pytest.raises(ValueError, match="inconnue"):
        apply_annotation_reviews(plan, (
            AnnotationReview("unknown", AnnotationReviewAction.KEEP),
        ))


def test_annotation_review_level_changes_label_metadata_and_severity():
    item = NotebookAnnotation(
        "level", AnnotationKind.FEEDBACK, FeedbackAudience.STUDENT,
        "Texte", ("source",), None, None, 0,
        AnnotationPlacement.AFTER_CELL, TeacherReportSeverity.INFO,
    )
    reviewed = apply_annotation_reviews(
        AnnotationPlan("project", "source", (item,)),
        (AnnotationReview(
            "level", AnnotationReviewAction.KEEP,
            level=AnnotationReviewLevel.TO_REVIEW,
        ),),
    ).annotations[0]
    assert reviewed.severity is TeacherReportSeverity.IMPORTANT
    assert dict(reviewed.metadata)["review_level"] == "to_review"
from tpstudio.feedback import FeedbackAudience
from tpstudio.reporting import TeacherReportSeverity


def _annotation():
    return NotebookAnnotation("tpstudio:test", AnnotationKind.FEEDBACK, FeedbackAudience.STUDENT, "Message exact", ("feedback-001",), "p", None, 2, AnnotationPlacement.APPEND_TO_MARKDOWN, TeacherReportSeverity.ATTENTION)


def test_enums_and_model_are_exact_and_immutable() -> None:
    assert AnnotationKind.FEEDBACK.value == "feedback"
    assert AnnotationPlacement.AFTER_CELL.value == "after_cell"
    item = _annotation()
    with pytest.raises(FrozenInstanceError): item.message = "x"
    assert not hasattr(item, "score") and not hasattr(item, "grade") and not hasattr(item, "path")


@pytest.mark.parametrize("field,value", (("annotation_id", " "), ("message", ""), ("target_cell_index", -1)))
def test_invalid_annotation_fields_are_rejected(field, value) -> None:
    values = dict(annotation_id="id", kind=AnnotationKind.FEEDBACK, audience=FeedbackAudience.STUDENT, message="m", source_ids=("s",), production_id="p", comparison_id=None, target_cell_index=0, placement=AnnotationPlacement.AFTER_CELL, severity=TeacherReportSeverity.INFO)
    values[field] = value
    with pytest.raises(ValueError): NotebookAnnotation(**values)


def test_options_require_exact_booleans_and_plan_rejects_duplicates() -> None:
    with pytest.raises(TypeError): AnnotationOptions(include_diagnostics=1)
    item = _annotation()
    with pytest.raises(ValueError): AnnotationPlan("project", "source", (item, item))
