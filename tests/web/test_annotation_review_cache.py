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
    load_shared_response_reviews,
    save_annotation_reviews,
    save_shared_response_reviews,
)
import nbformat


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


def test_shared_review_requires_same_question_and_identical_response(tmp_path):
    first_notebook = tmp_path / "first.ipynb"
    second_notebook = tmp_path / "second.ipynb"
    different_notebook = tmp_path / "different.ipynb"
    for path, response in (
        (first_notebook, "La période vaut 1,2 s."),
        (second_notebook, "  La période vaut 1,2 s.  "),
        (different_notebook, "La période vaut 1,3 s."),
    ):
        cells = [nbformat.v4.new_markdown_cell("Question") for _ in range(13)]
        cells[12].source = response
        nbformat.write(nbformat.v4.new_notebook(cells=cells), path)

    source_annotation = _annotation("annotation-copy-001")
    review = AnnotationReview(
        source_annotation.annotation_id,
        AnnotationReviewAction.KEEP,
        level=AnnotationReviewLevel.GOOD,
    )
    shared_dir = tmp_path / "shared"
    save_shared_response_reviews(
        first_notebook,
        (review,),
        (source_annotation,),
        cache_dir=shared_dir,
    )

    restored = load_shared_response_reviews(
        second_notebook,
        (_annotation("annotation-copy-002"),),
        cache_dir=shared_dir,
    )
    assert restored == (
        AnnotationReview(
            "annotation-copy-002",
            AnnotationReviewAction.KEEP,
            level=AnnotationReviewLevel.GOOD,
        ),
    )
    assert load_shared_response_reviews(
        different_notebook,
        (_annotation("annotation-copy-003"),),
        cache_dir=shared_dir,
    ) == ()


def test_shared_review_does_not_cross_questions(tmp_path):
    notebook = tmp_path / "copy.ipynb"
    cells = [nbformat.v4.new_markdown_cell("Même réponse") for _ in range(14)]
    nbformat.write(nbformat.v4.new_notebook(cells=cells), notebook)
    first = _annotation("annotation-1")
    second = NotebookAnnotation(
        annotation_id="annotation-2",
        kind=first.kind,
        audience=first.audience,
        message=first.message,
        source_ids=("semantic:other-question",),
        production_id="other-question",
        comparison_id=None,
        target_cell_index=13,
        placement=first.placement,
        severity=first.severity,
    )
    save_shared_response_reviews(
        notebook,
        (AnnotationReview(first.annotation_id, AnnotationReviewAction.KEEP),),
        (first,),
        cache_dir=tmp_path / "shared",
    )

    assert load_shared_response_reviews(
        notebook, (second,), cache_dir=tmp_path / "shared"
    ) == ()
