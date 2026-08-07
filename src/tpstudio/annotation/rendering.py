"""Deterministic Markdown rendering for TPStudio annotations."""

from __future__ import annotations

from .model import AnnotationPlacement, NotebookAnnotation


def render_notebook_annotation(annotation: NotebookAnnotation) -> str:
    if type(annotation) is not NotebookAnnotation:
        raise TypeError("Le rendu exige exactement une NotebookAnnotation.")
    if annotation.placement is AnnotationPlacement.APPEND_TO_MARKDOWN:
        return (
            f"<!-- TPSTUDIO:BEGIN annotation_id={annotation.annotation_id} -->\n"
            "---\n**Retour TPStudio**\n\n"
            f"{annotation.message}\n"
            f"<!-- TPSTUDIO:END annotation_id={annotation.annotation_id} -->"
        )
    return (
        f"<!-- TPSTUDIO:ANNOTATION annotation_id={annotation.annotation_id} -->\n"
        "**Retour TPStudio**\n\n"
        f"{annotation.message}"
    )
