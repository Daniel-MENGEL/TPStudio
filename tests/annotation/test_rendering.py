from tpstudio.annotation import AnnotationKind, AnnotationPlacement, NotebookAnnotation, render_notebook_annotation
from tpstudio.feedback import FeedbackAudience
from tpstudio.reporting import TeacherReportSeverity


def _item(placement):
    return NotebookAnnotation("tpstudio:stable", AnnotationKind.FEEDBACK, FeedbackAudience.STUDENT, "Message inchangé", ("f1",), "p", None, 0, placement, TeacherReportSeverity.INFO)


def test_appended_render_has_balanced_invisible_markers_and_exact_message() -> None:
    text = render_notebook_annotation(_item(AnnotationPlacement.APPEND_TO_MARKDOWN))
    assert "TPSTUDIO:BEGIN annotation_id=tpstudio:stable" in text
    assert "TPSTUDIO:END annotation_id=tpstudio:stable" in text
    assert "Message inchangé" in text and "score" not in text.lower()


def test_dedicated_render_is_deterministic() -> None:
    item = _item(AnnotationPlacement.AFTER_CELL)
    assert render_notebook_annotation(item) == render_notebook_annotation(item)
    text = render_notebook_annotation(item)
    assert text
    assert "TPSTUDIO:ANNOTATION" in text
