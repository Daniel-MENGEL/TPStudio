"""Pure adapter from UI selections to the A71g planning API."""

from __future__ import annotations

from pathlib import Path
import nbformat

from tpstudio.batch import BatchCopySource, BatchOptions, BatchPlan, build_batch_plan

from .identity import build_canonical_copy_stem, canonical_tp_name, identify_selected_copy
from .model import SelectedCopy, WebBatchOptions


class WebInputError(ValueError):
    """A safe, user-facing validation error created by the web layer."""


def validate_selected_notebook(copy: SelectedCopy) -> None:
    try:
        notebook = nbformat.read(copy.workspace_path, as_version=4)
        nbformat.validate(notebook)
    except Exception as exc:
        raise WebInputError("Notebook invalide.") from exc


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
