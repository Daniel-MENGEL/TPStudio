"""Pure adapter from UI selections to the A71g planning API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tpstudio.batch import BatchCopySource, BatchOptions, BatchPlan, build_batch_plan
from tpstudio.orchestration import BatchCopyRequest, NotebookCopySource, load_and_normalize_notebook
from tpstudio.projects import project_descriptor, resolve_project_for_copy

from .identity import build_canonical_copy_stem, canonical_tp_name, identify_selected_copy
from .model import SelectedCopy, WebBatchOptions


class WebInputError(ValueError):
    """A safe, user-facing validation error created by the web layer."""


@dataclass(frozen=True, slots=True)
class WebProjectPreview:
    project_id: str | None
    title: str
    requires_teacher_choice: bool


def project_preview_for_selected_copy(copy: SelectedCopy) -> WebProjectPreview:
    """Detect the likely TP during batch verification without running code."""

    notebook = load_and_normalize_notebook(copy.workspace_path)
    resolution = resolve_project_for_copy(
        notebook, filename=copy.original_filename,
    )
    if resolution.selected_project_id is not None:
        descriptor = project_descriptor(resolution.selected_project_id)
        return WebProjectPreview(
            resolution.selected_project_id,
            descriptor.title if descriptor is not None else resolution.selected_project_id,
            resolution.requires_teacher_choice,
        )
    candidates = tuple(
        project_descriptor(item.project_id)
        for item in resolution.candidates
    )
    candidate_titles = tuple(
        item.title for item in candidates if item is not None
    )
    if candidate_titles:
        return WebProjectPreview(
            None,
            "À confirmer : " + " / ".join(candidate_titles[:2]),
            True,
        )
    return WebProjectPreview(None, "Non reconnu", True)


def resolve_output_dir(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise WebInputError("Le dossier de sortie est vide.")
    try:
        path = Path(value).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise WebInputError("Le dossier de sortie est invalide.") from exc
    if path.exists() and not path.is_dir():
        raise WebInputError("Le dossier de sortie est invalide.")
    return path


def validate_selected_notebook(copy: SelectedCopy) -> None:
    try:
        load_and_normalize_notebook(copy.workspace_path)
    except Exception as exc:
        raise WebInputError(
            f"Notebook invalide : {copy.original_filename}."
        ) from exc


def build_batch_plan_from_web_selection(
    copies: tuple[SelectedCopy, ...],
    output_dir: Path,
    options: WebBatchOptions | None = None,
) -> BatchPlan:
    copies = tuple(copies)
    if not copies:
        raise ValueError("Aucune copie sélectionnée.")
    if not isinstance(output_dir, Path):
        raise TypeError("output_dir doit être un Path.")
    options = WebBatchOptions() if options is None else options
    if type(options) is not WebBatchOptions:
        raise TypeError("Les options web sont invalides.")
    for copy in copies:
        validate_selected_notebook(copy)
    identified = tuple(identify_selected_copy(item) if item.identity is None else item for item in copies)
    sources = tuple(
        BatchCopySource(
            item.source_id,
            item.workspace_path,
            item.original_filename,
            build_canonical_copy_stem(canonical_tp_name("snells-laws-mvp"), item.identity) if item.identity else None,
        )
        for item in identified
    )
    batch_options = BatchOptions(
        overwrite=options.overwrite,
        continue_on_error=True,
        include_teacher_feedback=options.include_teacher_feedback,
        include_diagnostics=options.include_diagnostics,
        hide_code=options.hide_code,
        hide_outputs=options.hide_outputs,
    )
    return build_batch_plan(sources, output_dir, batch_options)


def build_dispatch_requests_from_web_selection(copies: tuple[SelectedCopy, ...]) -> tuple[BatchCopyRequest, ...]:
    """Convert selected uploads to project-agnostic analysis requests."""
    copies = tuple(copies)
    if not copies:
        raise ValueError("Aucune copie sélectionnée.")
    return tuple(
        BatchCopyRequest(
            item.source_id,
            NotebookCopySource(item.source_id, item.original_filename, item.workspace_path),
        )
        for item in copies
    )
