"""Transactional A71f export pipeline."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import os
from pathlib import Path
import tempfile
import unicodedata
from dataclasses import replace

import nbformat

from tpstudio.annotation import (
    AnnotationOptions, AnnotationPlan, AnnotationReview,
    apply_annotation_plan,
    apply_annotation_reviews, build_annotation_plan,
)
from tpstudio.orchestration import (
    CopyAnalysisResult, NotebookCopySource, analyze_snells_laws_copy, load_notebook_copy,
)
from tpstudio.interpretation import apply_interpretation_reviews
from tpstudio.interpretation import InterpretationDiagnostic, InterpretationFeedbackItem
from tpstudio.reporting import build_teacher_copy_report
from tpstudio.review_store import load_interpretation_reviews, review_store_path
from tpstudio.semantic_analysis import strip_standalone_response_placeholders

from .html import render_annotated_notebook_html
from .model import CopyExportOptions, CopyExportResult, ExportArtifact, ExportArtifactKind
from .notebook import default_export_names, validate_exported_notebook, validate_notebook_object


def _same_location(first: Path, second: Path) -> bool:
    return first.resolve() == second.resolve()


def _inside_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def _compact_present_schematic_feedback(plan: AnnotationPlan) -> AnnotationPlan:
    """Keep only the appreciation in student exports for present schematics."""

    def compact(items):
        result = []
        for item in items:
            metadata = dict(item.metadata)
            if (
                metadata.get("origin") == "attachment_check"
                and item.message.startswith("Schéma inséré :")
            ):
                item = replace(
                    item,
                    metadata=tuple(
                        pair for pair in item.metadata if pair[0] != "label_only"
                    ) + (("label_only", "true"),),
                )
            result.append(item)
        return tuple(result)

    return replace(
        plan,
        annotations=compact(plan.annotations),
        summary_annotations=compact(plan.summary_annotations),
    )


def _without_submission_instructions(notebook):
    """Remove pre-submission reminders from an already corrected copy."""

    def normalized(value: str) -> str:
        value = unicodedata.normalize("NFKD", value)
        value = "".join(character for character in value if not unicodedata.combining(character))
        return value.casefold().replace("’", "'")

    removable_markers = (
        "liste d'auto-verification avant rendu",
        "notebook termine ?",
        "deposer le notebook complete",
        "dropbox.com/request/",
    )
    filtered = deepcopy(notebook)
    filtered.cells = [
        cell
        for cell in notebook.cells
        if not (
            cell.cell_type == "markdown"
            and any(
                marker in normalized(str(cell.source))
                for marker in removable_markers
            )
        )
    ]
    return filtered


def _without_response_placeholders(notebook):
    """Hide unused answer-template lines in corrected previews and exports."""

    filtered = deepcopy(notebook)
    for cell in filtered.cells:
        if cell.cell_type == "markdown":
            cell.source = strip_standalone_response_placeholders(str(cell.source))
    return filtered


def _with_final_grade(notebook, grade: str | None, session_average: str | None = None):
    """Append the teacher-facing grade as the final corrected-copy block."""

    if grade is None:
        return notebook
    grade = grade.strip()
    if not grade:
        return notebook
    if not grade.endswith("/20"):
        grade = f"{grade}/20"
    average_html = ""
    if session_average is not None and session_average.strip():
        average = session_average.strip()
        if not average.endswith("/20"):
            average = f"{average}/20"
        average_html = f'<br><span>Moyenne des copies corrigées de ce TP : {average}</span>'
    result = deepcopy(notebook)
    result.cells.append(nbformat.v4.new_markdown_cell(
        '<div class="tpstudio-final-grade" '
        'style="margin-top:2em;padding:1em 1.2em;border:2px solid #334155;'
        'border-radius:6px;background:#f8fafc;font-size:1.15em">'
        f'<strong>Note : {grade}</strong>{average_html}</div>'
    ))
    return result


def _write_temp(directory: Path, suffix: str, content: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=".tpstudio-", suffix=suffix, dir=directory)
    with os.fdopen(handle, "wb") as stream:
        stream.write(content)
    return Path(name)


def _commit_artifact_pair(
    temp_notebook: Path,
    notebook_path: Path,
    temp_html: Path,
    html_path: Path,
    *,
    overwrite: bool,
) -> None:
    """Install two prepared files, restoring both destinations on failure."""
    backups: dict[Path, Path] = {}
    installed: list[Path] = []
    try:
        if overwrite:
            for destination in (notebook_path, html_path):
                if destination.exists():
                    handle, name = tempfile.mkstemp(prefix=".tpstudio-backup-", dir=destination.parent)
                    os.close(handle)
                    backup = Path(name)
                    backup.unlink()
                    os.replace(destination, backup)
                    backups[destination] = backup
        os.replace(temp_notebook, notebook_path)
        installed.append(notebook_path)
        os.replace(temp_html, html_path)
        installed.append(html_path)
    except Exception:
        for destination in installed:
            destination.unlink(missing_ok=True)
        for destination, backup in backups.items():
            if backup.exists():
                os.replace(backup, destination)
        temp_notebook.unlink(missing_ok=True)
        temp_html.unlink(missing_ok=True)
        for backup in backups.values():
            backup.unlink(missing_ok=True)
        raise
    else:
        for backup in backups.values():
            backup.unlink(missing_ok=True)


def export_snells_laws_copy(
    source_path: Path,
    output_dir: Path,
    *,
    source_id: str = "local-copy",
    options: CopyExportOptions | None = None,
    notebook_output_path: Path | None = None,
    html_output_path: Path | None = None,
) -> CopyExportResult:
    if not isinstance(source_path, Path) or not isinstance(output_dir, Path):
        raise TypeError("source_path et output_dir doivent être des pathlib.Path.")
    source = NotebookCopySource(source_id, source_path.name, source_path)
    analysis = analyze_snells_laws_copy(source)
    return export_analyzed_copy(
        source, analysis, output_dir, options=options,
        notebook_output_path=notebook_output_path,
        html_output_path=html_output_path,
    )


def export_analyzed_copy(
    source: NotebookCopySource,
    analysis: CopyAnalysisResult,
    output_dir: Path,
    *,
    options: CopyExportOptions | None = None,
    output_stem: str | None = None,
    notebook_output_path: Path | None = None,
    html_output_path: Path | None = None,
    annotation_reviews: tuple[AnnotationReview, ...] = (),
    grade: str | None = None,
    session_average: str | None = None,
) -> CopyExportResult:
    """Export an already completed analysis without running analysis again."""
    if not isinstance(source, NotebookCopySource):
        raise TypeError("source doit être un NotebookCopySource.")
    if type(analysis) is not CopyAnalysisResult:
        raise TypeError("analysis doit être un CopyAnalysisResult.")
    if not isinstance(output_dir, Path):
        raise TypeError("output_dir doit être un pathlib.Path.")
    if (
        source.source_id != analysis.source_id
        or source.path.resolve() != analysis.source.path.resolve()
    ):
        raise ValueError("source et analysis ne désignent pas la même copie.")
    options = CopyExportOptions() if options is None else options
    if type(options) is not CopyExportOptions:
        raise TypeError("Les options d'export sont invalides.")
    if (notebook_output_path is None) != (html_output_path is None):
        raise ValueError("Les deux destinations explicites doivent être fournies ensemble.")
    if notebook_output_path is None:
        name = source.display_name if output_stem is None else output_stem
        notebook_name, html_name = default_export_names(name)
        notebook_path, html_path = output_dir / notebook_name, output_dir / html_name
    else:
        if output_stem is not None:
            raise ValueError("output_stem et destinations explicites sont mutuellement exclusifs.")
        if not isinstance(notebook_output_path, Path) or not isinstance(html_output_path, Path):
            raise TypeError("Les destinations explicites doivent être des pathlib.Path.")
        notebook_path, html_path = notebook_output_path, html_output_path
        if not _inside_directory(notebook_path, output_dir) or not _inside_directory(html_path, output_dir):
            raise ValueError("Les destinations explicites doivent rester dans output_dir.")
    if _same_location(notebook_path, source.path) or _same_location(html_path, source.path):
        raise ValueError("Une destination d'export ne peut pas être le notebook source.")
    if _same_location(notebook_path, html_path):
        raise ValueError("Les destinations notebook et HTML doivent être distinctes.")
    notebook_existed = notebook_path.exists()
    html_existed = html_path.exists()
    if not options.overwrite and (
        html_existed
        or (options.include_notebook and notebook_existed)
    ):
        raise FileExistsError("Une destination d'export existe déjà.")

    before = sha256(source.path.read_bytes()).digest()
    persisted_reviews = load_interpretation_reviews(review_store_path(output_dir))
    effective_evaluations, effective_traces, interpretation_diagnostics, interpretation_feedback = apply_interpretation_reviews(
        analysis.interpretation_response_evaluations,
        analysis.interpretation_review_traces,
        persisted_reviews,
    )
    non_interpretation_diagnostics = tuple(
        item for item in analysis.diagnostics
        if not isinstance(item, InterpretationDiagnostic)
    )
    non_interpretation_feedback = tuple(
        item for item in analysis.feedback
        if not isinstance(item, InterpretationFeedbackItem)
    )
    analysis = replace(
        analysis,
        interpretation_response_evaluations=effective_evaluations,
        interpretation_review_traces=effective_traces,
        diagnostics=non_interpretation_diagnostics + interpretation_diagnostics,
        feedback=non_interpretation_feedback + interpretation_feedback,
    )
    report = build_teacher_copy_report(analysis)
    annotation_options = AnnotationOptions(
        include_teacher_feedback=options.include_teacher_feedback,
        include_diagnostics=options.include_diagnostics,
        include_limitations=options.include_limitations,
    )
    plan = apply_annotation_reviews(
        build_annotation_plan(analysis, report, annotation_options),
        annotation_reviews,
    )
    plan = _compact_present_schematic_feedback(plan)
    original_notebook = load_notebook_copy(source)
    annotated = apply_annotation_plan(original_notebook, plan, annotation_options)
    corrected_notebook = _with_final_grade(
        _without_response_placeholders(
            _without_submission_instructions(annotated.notebook)
        ),
        grade,
        session_average,
    )
    notebook_validation = validate_notebook_object(corrected_notebook)
    if not notebook_validation.valid:
        raise ValueError("Le notebook annoté est invalide.")
    title = f"{analysis.project.identity.title} — Correction"
    html = render_annotated_notebook_html(corrected_notebook, options=options, title=title)
    if not html.strip():
        raise ValueError("Le rendu HTML est vide.")

    temp_html = _write_temp(output_dir, ".html", html.encode("utf-8"))
    if options.include_notebook:
        notebook_bytes = nbformat.writes(corrected_notebook).encode("utf-8")
        temp_notebook = _write_temp(output_dir, ".ipynb", notebook_bytes)
        exported_validation = validate_exported_notebook(temp_notebook)
        if not exported_validation.valid:
            temp_notebook.unlink(missing_ok=True)
            temp_html.unlink(missing_ok=True)
            raise ValueError("Le notebook temporaire est invalide avant écriture.")
        _commit_artifact_pair(
            temp_notebook, notebook_path, temp_html, html_path,
            overwrite=options.overwrite,
        )
    else:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            temp_html.replace(html_path)
        finally:
            temp_html.unlink(missing_ok=True)
    after = sha256(source.path.read_bytes()).digest()
    if before != after:
        raise RuntimeError("Le notebook source a été modifié pendant l'export.")
    student = sum(item.audience.value == "student" for item in plan.annotations)
    teacher = sum(item.audience.value == "teacher" for item in plan.annotations)
    return CopyExportResult(
        analysis.project_id, analysis.source_id,
        ExportArtifact(ExportArtifactKind.NOTEBOOK, notebook_path, options.include_notebook, options.include_notebook and options.overwrite and notebook_existed, "application/x-ipynb+json", analysis.source_id),
        ExportArtifact(ExportArtifactKind.HTML, html_path, True, options.overwrite and html_existed, "text/html", analysis.source_id, (("delivery", "email-attachment-ready"),)),
        plan.count, student, teacher, before == after, True, True,
        tuple(analysis.limitations), analysis.interpretation_review_traces,
        report,
    )


def render_analyzed_copy_html(
    source: NotebookCopySource,
    analysis: CopyAnalysisResult,
    *,
    options: CopyExportOptions | None = None,
    annotation_reviews: tuple[AnnotationReview, ...] = (),
) -> str:
    """Render a read-only reviewed preview without creating an artifact."""

    if not isinstance(source, NotebookCopySource):
        raise TypeError("source doit être un NotebookCopySource.")
    if type(analysis) is not CopyAnalysisResult:
        raise TypeError("analysis doit être un CopyAnalysisResult.")
    if (
        source.source_id != analysis.source_id
        or source.path.resolve() != analysis.source.path.resolve()
    ):
        raise ValueError("source et analysis ne désignent pas la même copie.")
    options = CopyExportOptions() if options is None else options
    if type(options) is not CopyExportOptions:
        raise TypeError("Les options d'aperçu sont invalides.")
    report = build_teacher_copy_report(analysis)
    annotation_options = AnnotationOptions(
        include_teacher_feedback=options.include_teacher_feedback,
        include_diagnostics=options.include_diagnostics,
        include_limitations=options.include_limitations,
    )
    plan = apply_annotation_reviews(
        build_annotation_plan(analysis, report, annotation_options),
        annotation_reviews,
    )
    original = load_notebook_copy(source)
    annotated = apply_annotation_plan(original, plan, annotation_options)
    title = f"{analysis.project.identity.title} — Aperçu corrigé"
    corrected_notebook = _without_response_placeholders(annotated.notebook)
    return render_annotated_notebook_html(corrected_notebook, options=options, title=title)


def summarize_copy_export(result: CopyExportResult) -> str:
    if type(result) is not CopyExportResult:
        raise TypeError("Le résultat d'export est invalide.")
    return "\n".join((
        f"Project: {result.project_id}", f"Source: {result.source_id}",
        f"Notebook: {'created' if result.notebook_artifact.created else 'not created'}",
        f"HTML: {'created' if result.html_generated else 'not created'}",
        f"Annotations: {result.student_annotation_count} student, {result.teacher_annotation_count} teacher",
        f"Source preserved: {'yes' if result.source_preserved else 'no'}",
        f"Notebook valid: {'yes' if result.notebook_valid else 'no'}",
        f"HTML generated: {'yes' if result.html_generated else 'no'}",
        f"Limitations: {len(result.limitations)}",
    ))
