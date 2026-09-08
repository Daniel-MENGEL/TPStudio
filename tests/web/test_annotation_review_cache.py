from tpstudio.annotation import (
    AnnotationKind,
    AnnotationPlacement,
    AnnotationReview,
    AnnotationReviewAction,
    AnnotationReviewLevel,
    NotebookAnnotation,
)
from tpstudio.feedback import FeedbackAudience
from tpstudio.reporting import TeacherReportSeverity
from tpstudio.web.annotation_review_cache import (
    load_annotation_reviews,
    save_annotation_reviews,
)


def _annotation(annotation_id: str, message: str = "À compléter"):
    return NotebookAnnotation(
        annotation_id=annotation_id,
        kind=AnnotationKind.FEEDBACK,
        audience=FeedbackAudience.STUDENT,
        message=message,
        source_ids=("semantic:period",),
        production_id="period",
        comparison_id=None,
        target_cell_index=12,
        placement=AnnotationPlacement.AFTER_CELL,
        severity=TeacherReportSeverity.ATTENTION,
    )


def test_annotation_reviews_survive_source_id_changes(tmp_path):
    first = _annotation("annotation-copy-001")
    review = AnnotationReview(
        first.annotation_id,
        AnnotationReviewAction.EDIT,
        "Commentaire du professeur",
        AnnotationReviewLevel.GOOD,
    )
    digest = "a" * 64

    save_annotation_reviews(
        digest, (review,), (first,), cache_dir=tmp_path
    )
    restored = load_annotation_reviews(
        digest, (_annotation("annotation-copy-009"),), cache_dir=tmp_path
    )

    assert restored == (
        AnnotationReview(
            "annotation-copy-009",
            AnnotationReviewAction.EDIT,
            "Commentaire du professeur",
            AnnotationReviewLevel.GOOD,
        ),
    )


def test_annotation_review_cache_invalidates_changed_expectation(tmp_path):
    annotation = _annotation("annotation-copy-001")
    save_annotation_reviews(
        "b" * 64,
        (AnnotationReview(annotation.annotation_id, AnnotationReviewAction.KEEP),),
        (annotation,),
        cache_dir=tmp_path,
    )

    assert load_annotation_reviews(
        "b" * 64,
        (_annotation("annotation-copy-001", "Nouvelle attente"),),
        cache_dir=tmp_path,
    ) == ()
