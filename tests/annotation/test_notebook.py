from copy import deepcopy

import nbformat

from tpstudio.annotation import (
    AnnotationKind, AnnotationOptions, AnnotationPlacement, AnnotationPlan,
    NotebookAnnotation, apply_annotation_plan, find_tpstudio_annotations,
    remove_tpstudio_annotations,
)
from tpstudio.feedback import FeedbackAudience
from tpstudio.reporting import TeacherReportSeverity


def _annotation(identifier, index, placement, message="Message"):
    return NotebookAnnotation(identifier, AnnotationKind.FEEDBACK, FeedbackAudience.STUDENT, message, ("f",), "p", None, index, placement, TeacherReportSeverity.ATTENTION)


def _notebook():
    code = nbformat.v4.new_code_cell("x = 1", execution_count=3, outputs=[nbformat.v4.new_output("execute_result", data={"text/plain": "1"}, execution_count=3)])
    markdown = nbformat.v4.new_markdown_cell("Réponse étudiante")
    markdown.attachments = {"image.png": {"image/png": "AA=="}}
    return nbformat.v4.new_notebook(cells=[markdown, code], metadata={"kernelspec": {"name": "python3", "display_name": "Python", "language": "python"}})


def test_append_and_remove_restore_markdown_exactly() -> None:
    source = _notebook(); original = deepcopy(source)
    plan = AnnotationPlan("p", "s", (_annotation("a", 0, AnnotationPlacement.APPEND_TO_MARKDOWN),))
    result = apply_annotation_plan(source, plan)
    assert result.notebook.cells[0].source.startswith("Réponse étudiante\n\n")
    assert remove_tpstudio_annotations(result.notebook) == original
    assert source == original


def test_code_is_unchanged_and_annotation_cell_is_added_after() -> None:
    source = _notebook(); original_code = deepcopy(source.cells[1])
    plan = AnnotationPlan("p", "s", (_annotation("a", 1, AnnotationPlacement.AFTER_CELL),))
    result = apply_annotation_plan(source, plan)
    assert result.notebook.cells[1] == original_code
    assert result.notebook.cells[2].metadata.tpstudio.annotation is True
    assert result.notebook.cells[2].cell_type == "markdown"


def test_application_is_idempotent_and_updates_stable_annotation() -> None:
    source = _notebook()
    first_plan = AnnotationPlan("p", "s", (_annotation("stable", 0, AnnotationPlacement.APPEND_TO_MARKDOWN, "Ancien"),))
    second_plan = AnnotationPlan("p", "s", (_annotation("stable", 0, AnnotationPlacement.APPEND_TO_MARKDOWN, "Nouveau"),))
    first = apply_annotation_plan(source, first_plan)
    repeated = apply_annotation_plan(first.notebook, first_plan)
    assert repeated.notebook == first.notebook
    updated = apply_annotation_plan(first.notebook, second_plan)
    assert "Ancien" not in updated.notebook.cells[0].source and "Nouveau" in updated.notebook.cells[0].source


def test_orphans_removed_or_kept_according_to_option() -> None:
    source = _notebook(); old = AnnotationPlan("p", "s", (_annotation("old", 1, AnnotationPlacement.AFTER_CELL),))
    derived = apply_annotation_plan(source, old).notebook
    empty = AnnotationPlan("p", "s", ())
    assert not find_tpstudio_annotations(apply_annotation_plan(derived, empty).notebook)
    kept = apply_annotation_plan(derived, empty, AnnotationOptions(replace_existing_tpstudio_annotations=False))
    assert find_tpstudio_annotations(kept.notebook)


def test_student_text_mention_is_not_a_marker() -> None:
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("Je parle de TPStudio sans marqueur.")])
    assert find_tpstudio_annotations(notebook) == ()
    assert remove_tpstudio_annotations(notebook) == notebook


def test_multiple_annotations_keep_plan_order_and_notebook_metadata() -> None:
    source = _notebook(); original_metadata = deepcopy(source.metadata)
    plan = AnnotationPlan("p", "s", (
        _annotation("one", 1, AnnotationPlacement.AFTER_CELL, "Premier"),
        _annotation("two", 1, AnnotationPlacement.AFTER_CELL, "Second"),
    ))
    result = apply_annotation_plan(source, plan)
    assert "Premier" in result.notebook.cells[2].source
    assert "Second" in result.notebook.cells[3].source
    assert result.notebook.metadata == original_metadata
