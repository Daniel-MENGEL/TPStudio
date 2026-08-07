from dataclasses import FrozenInstanceError

import pytest

from tpstudio.annotation import (
    AnnotationKind, AnnotationOptions, AnnotationPlacement, AnnotationPlan,
    NotebookAnnotation,
)
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
