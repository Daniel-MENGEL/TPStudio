"""Deterministic Markdown rendering for TPStudio annotations."""

from __future__ import annotations

import html

from .model import AnnotationPlacement, NotebookAnnotation
from tpstudio.reporting import TeacherReportSeverity


_PRESENTATION = {
    TeacherReportSeverity.INFO: ("info", "Très bien"),
    TeacherReportSeverity.ATTENTION: ("attention", "À vérifier"),
    TeacherReportSeverity.IMPORTANT: ("important", "Remarque"),
    TeacherReportSeverity.BLOCKING: ("blocking", "Problème"),
}

_REVIEW_LABELS = {
    "absent": "Absence de réponse",
    "to_review": "À revoir",
    "partial": "Partiel",
    "good": "Bien",
    "very_good": "Très bien",
}

_ANNOTATION_CSS = """<style>
.tpstudio-annotation { margin: .8em 0; padding: .65em .9em; border-left: .35em solid; scroll-margin: 4em; }
.tpstudio-review-focus { outline: .28em solid #7c3aed; box-shadow: 0 0 0 .45em rgba(124,58,237,.18); }
.tpstudio-severity-info { background: #edf7ee; border-color: #6aa56f; }
.tpstudio-severity-important { background: #eef5fb; border-color: #6c9bc4; }
.tpstudio-severity-attention { background: #fff8e6; border-color: #c59a3b; }
.tpstudio-severity-blocking { background: #fceeee; border-color: #c76b6b; }
@media print { .tpstudio-annotation { background: transparent !important; } }
</style>"""

_INLINE_STYLES = {
    "info": "background:#edf7ee;border-left:.35em solid #6aa56f",
    "important": "background:#eef5fb;border-left:.35em solid #6c9bc4",
    "attention": "background:#fff8e6;border-left:.35em solid #c59a3b",
    "blocking": "background:#fceeee;border-left:.35em solid #c76b6b",
}


def annotation_presentation(annotation: NotebookAnnotation) -> tuple[str, str]:
    if type(annotation) is not NotebookAnnotation:
        raise TypeError("Le rendu exige exactement une NotebookAnnotation.")
    style, label = _PRESENTATION[annotation.severity]
    review_level = dict(annotation.metadata).get("review_level")
    return style, _REVIEW_LABELS.get(review_level, label)


def annotation_css() -> str:
    return _ANNOTATION_CSS


def render_notebook_annotation(annotation: NotebookAnnotation) -> str:
    if type(annotation) is not NotebookAnnotation:
        raise TypeError("Le rendu exige exactement une NotebookAnnotation.")
    style, label = annotation_presentation(annotation)
    safe_message = html.escape(annotation.message, quote=False)
    content = (
        f'<blockquote id="{html.escape(annotation.annotation_id, quote=True)}" '
        f'class="tpstudio-annotation tpstudio-severity-{style}" role="note" '
        f'style="{_INLINE_STYLES[style]}">\n'
        f"<strong>{label}</strong>\n\n"
        f"{safe_message}\n"
        "</blockquote>"
    )
    if annotation.placement is AnnotationPlacement.APPEND_TO_MARKDOWN:
        return (
            f"<!-- TPSTUDIO:BEGIN annotation_id={annotation.annotation_id} -->\n"
            f"{content}\n"
            f"<!-- TPSTUDIO:END annotation_id={annotation.annotation_id} -->"
        )
    return (
        f"<!-- TPSTUDIO:ANNOTATION annotation_id={annotation.annotation_id} -->\n"
        f"{content}"
    )
