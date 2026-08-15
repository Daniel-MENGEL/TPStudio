"""Transactional A71f export pipeline."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import tempfile
from dataclasses import replace

import nbformat

from tpstudio.annotation import (
    AnnotationOptions, apply_annotation_plan, build_annotation_plan,
)
from tpstudio.orchestration import (
    NotebookCopySource, analyze_snells_laws_copy, load_notebook_copy,
)
from tpstudio.interpretation import apply_interpretation_reviews
from tpstudio.interpretation import InterpretationDiagnostic, InterpretationFeedbackItem
from tpstudio.reporting import build_teacher_copy_report
from tpstudio.review_store import load_interpretation_reviews, review_store_path

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
    options = CopyExportOptions() if options is None else options
    if type(options) is not CopyExportOptions:
        raise TypeError("Les options d'export sont invalides.")
    if (notebook_output_path is None) != (html_output_path is None):
        raise ValueError("Les deux destinations explicites doivent être fournies ensemble.")
    if notebook_output_path is None:
        notebook_name, html_name = default_export_names(source_path.name)
        notebook_path, html_path = output_dir / notebook_name, output_dir / html_name
    else:
        if not isinstance(notebook_output_path, Path) or not isinstance(html_output_path, Path):
            raise TypeError("Les destinations explicites doivent être des pathlib.Path.")
        notebook_path, html_path = notebook_output_path, html_output_path
        if not _inside_directory(notebook_path, output_dir) or not _inside_directory(html_path, output_dir):
            raise ValueError("Les destinations explicites doivent rester dans output_dir.")
    if _same_location(notebook_path, source_path) or _same_location(html_path, source_path):
        raise ValueError("Une destination d'export ne peut pas être le notebook source.")
    if _same_location(notebook_path, html_path):
        raise ValueError("Les destinations notebook et HTML doivent être distinctes.")
    notebook_existed = notebook_path.exists()
    html_existed = html_path.exists()
    if not options.overwrite and (notebook_existed or html_existed):
        raise FileExistsError("Une destination d'export existe déjà.")

    before = sha256(source_path.read_bytes()).digest()
    source = NotebookCopySource(source_id, source_path.name, source_path)
    analysis = analyze_snells_laws_copy(source)
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
    plan = build_annotation_plan(analysis, report, annotation_options)
    original_notebook = load_notebook_copy(source)
    annotated = apply_annotation_plan(original_notebook, plan, annotation_options)
    notebook_validation = validate_notebook_object(annotated.notebook)
    if not notebook_validation.valid:
        raise ValueError("Le notebook annoté est invalide.")
    html = render_annotated_notebook_html(annotated.notebook, options=options)
    if not html.strip():
        raise ValueError("Le rendu HTML est vide.")

    notebook_bytes = nbformat.writes(annotated.notebook).encode("utf-8")
    temp_notebook = _write_temp(output_dir, ".ipynb", notebook_bytes)
    temp_html = _write_temp(output_dir, ".html", html.encode("utf-8"))
    exported_validation = validate_exported_notebook(temp_notebook)
    if not exported_validation.valid:
        temp_notebook.unlink(missing_ok=True)
        temp_html.unlink(missing_ok=True)
        raise ValueError("Le notebook temporaire est invalide avant écriture.")
    _commit_artifact_pair(
        temp_notebook, notebook_path, temp_html, html_path,
        overwrite=options.overwrite,
    )
    after = sha256(source_path.read_bytes()).digest()
    if before != after:
        raise RuntimeError("Le notebook source a été modifié pendant l'export.")
    student = sum(item.audience.value == "student" for item in plan.annotations)
    teacher = sum(item.audience.value == "teacher" for item in plan.annotations)
    return CopyExportResult(
        analysis.project_id, analysis.source_id,
        ExportArtifact(ExportArtifactKind.NOTEBOOK, notebook_path, True, options.overwrite and notebook_existed, "application/x-ipynb+json", analysis.source_id),
        ExportArtifact(ExportArtifactKind.HTML, html_path, True, options.overwrite and html_existed, "text/html", analysis.source_id),
        plan.count, student, teacher, before == after, True, True,
        tuple(analysis.limitations), analysis.interpretation_review_traces,
    )


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
