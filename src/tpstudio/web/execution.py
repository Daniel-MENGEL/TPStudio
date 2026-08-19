"""Execution adapter for the prepared A71g batch; no scientific logic."""

from __future__ import annotations

from pathlib import Path
import re

from tpstudio.batch import BatchPlan, BatchRunResult, run_snells_laws_batch
from tpstudio.export import CopyExportOptions, export_analyzed_copy
from tpstudio.orchestration import BatchDispatchResult, CopyAnalysisOptions, NotebookCopySource, analyze_copy, run_batch
from tpstudio.projects import project_descriptor

from .planning import build_dispatch_requests_from_web_selection
from .model import WebCopyExportState, WebCopyOverride
from .presenters import active_analysis_for_source


def run_prepared_batch(plan: BatchPlan) -> BatchRunResult:
    if type(plan) is not BatchPlan:
        raise TypeError("Le lancement web exige un BatchPlan.")
    return run_snells_laws_batch(plan)


def run_selected_dispatch(copies, *, options: CopyAnalysisOptions | None = None, continue_on_error: bool = True) -> BatchDispatchResult:
    """Analyze selected copies generically, without export side effects."""
    return run_batch(
        build_dispatch_requests_from_web_selection(tuple(copies)),
        options=options,
        continue_on_error=continue_on_error,
    )


def analyze_selected_copy(
    source: NotebookCopySource,
    project_id: str,
    *,
    options: CopyAnalysisOptions | None = None,
):
    """Re-analyze one copy with the teacher-selected project."""
    descriptor = project_descriptor(project_id)
    if descriptor is None:
        raise ValueError("Projet inconnu.")
    return analyze_copy(source, project=descriptor.factory(), options=options)


def export_output_stem(analysis) -> str:
    """Build a deterministic project-agnostic stem for one active copy."""
    name = Path(analysis.source.display_name).stem
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._") or "copy"
    return f"{safe}-{analysis.source.source_id}"


def export_active_copies(
    result: BatchDispatchResult,
    overrides: dict[str, WebCopyOverride],
    *,
    output_dir: Path,
    options: CopyExportOptions,
) -> dict[str, WebCopyExportState]:
    """Export active analyses only; analysis and dispatch are never called here."""
    exported: dict[str, WebCopyExportState] = {}
    for item in result.copies:
        analysis = active_analysis_for_source(result, overrides, item.source_id)
        if analysis is None:
            continue
        try:
            exported[item.source_id] = WebCopyExportState(
                item.source_id,
                export_analyzed_copy(
                    analysis.source,
                    analysis,
                    output_dir,
                    options=options,
                    output_stem=export_output_stem(analysis),
                ),
            )
        except Exception as exc:
            exported[item.source_id] = WebCopyExportState(
                item.source_id,
                error_type=type(exc).__name__,
                error_message=str(exc)[:240] or type(exc).__name__,
            )
    return exported


def can_run_batch(selected_copies, plan) -> tuple[bool, tuple[str, ...]]:
    if plan is None:
        return False, ("Lot non vérifié.",)
    copies = tuple(selected_copies)
    if not copies:
        return False, ("Aucune copie sélectionnée.",)
    if tuple(item.source_id for item in copies) != tuple(source.source_id for source in plan.sources):
        return False, ("Le lot préparé est périmé.",)
    reasons = []
    for item in copies:
        identity = item.identity
        if identity is None or identity.status.value == "missing":
            reasons.append("Certaines identités sont manquantes.")
        elif identity.status.value == "to_review":
            reasons.append("Certaines identités doivent être vérifiées avant correction.")
    return (not reasons, tuple(dict.fromkeys(reasons)))
