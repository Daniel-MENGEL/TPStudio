"""Sequential runner delegating every copy to A71f."""

from __future__ import annotations

from tpstudio.export import export_snells_laws_copy

from .model import BatchCopyResult, BatchCopyStatus, BatchPlan, BatchRunResult


def run_snells_laws_batch(plan: BatchPlan) -> BatchRunResult:
    if type(plan) is not BatchPlan:
        raise TypeError("Le runner exige un BatchPlan.")
    results = []
    started = 0
    stopped = False
    for source, output in zip(plan.sources, plan.planned_outputs):
        if stopped:
            results.append(BatchCopyResult(
                source.source_id, BatchCopyStatus.SKIPPED,
                error_message="Copie non traitée après l'arrêt demandé du lot.",
            ))
            continue
        if not plan.options.overwrite and (output.notebook_path.exists() or output.html_path.exists()):
            result = BatchCopyResult(
                source.source_id, BatchCopyStatus.SKIPPED,
                error_message="Une destination existe déjà et overwrite est désactivé.",
            )
            results.append(result)
            if not plan.options.continue_on_error:
                stopped = True
            continue
        started += 1
        try:
            exported = export_snells_laws_copy(
                source.path, plan.output_dir,
                options=plan.options.export_options(),
                notebook_output_path=output.notebook_path,
                html_output_path=output.html_path,
            )
            if exported.notebook_artifact.path != output.notebook_path or exported.html_artifact.path != output.html_path:
                raise RuntimeError("L'export unitaire n'a pas respecté le plan de lot.")
            result = BatchCopyResult(
                source.source_id, BatchCopyStatus.SUCCESS,
                exported.notebook_artifact.path, exported.html_artifact.path,
                exported.annotation_count, None, exported.limitations,
            )
        except Exception as exc:
            result = BatchCopyResult(
                source.source_id, BatchCopyStatus.FAILED,
                error_type=type(exc).__name__,
                error_message=sanitize_batch_error_message(exc, source=source, output_dir=plan.output_dir),
            )
            if not plan.options.continue_on_error:
                stopped = True
        results.append(result)
    results = tuple(results)
    return BatchRunResult(
        "snells-laws-mvp", results, plan.output_dir, started,
        sum(item.status is BatchCopyStatus.SUCCESS for item in results),
        sum(item.status is BatchCopyStatus.FAILED for item in results),
        sum(item.status is BatchCopyStatus.SKIPPED for item in results),
        sum(item.annotation_count for item in results),
        sum(item.requires_human_review is True for item in results),
    )


def sanitize_batch_error_message(exc: BaseException, *, source, output_dir) -> str:
    """Map export failures to short, non-private public messages."""
    if isinstance(exc, FileNotFoundError):
        return "Impossible de lire la copie."
    if isinstance(exc, ValueError):
        text = str(exc).lower()
        if "notebook" in text and ("valide" in text or "invalid" in text):
            return "Notebook invalide."
        if "destination" in text or "existe déjà" in text:
            return "Une destination existe déjà."
        return "Échec d'export."
    if isinstance(exc, OSError):
        return "Échec d'écriture des artefacts."
    return "Échec d'export."
