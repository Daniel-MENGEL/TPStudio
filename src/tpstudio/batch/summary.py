"""Anonymized deterministic batch summaries."""

from __future__ import annotations

from pathlib import Path

from .model import BatchCopyStatus, BatchRunResult

def _human_review_label(value: bool | None) -> str:
    if value is True:
        return "oui"
    if value is False:
        return "non"
    return "indéterminée"


def summarize_batch_run(result: BatchRunResult) -> str:
    lines = [
        f"Project: {result.project_id}", f"Copies: {len(result.results)}",
        f"Success: {result.success_count}", f"Failed: {result.failed_count}",
        f"Skipped: {result.skipped_count}", f"Annotations: {result.total_annotation_count}",
        f"Human review confirmed: {result.human_review_count}", "", "Per copy:",
    ]
    for item in result.results:
        suffix = f" — {item.error_message}" if item.status is not BatchCopyStatus.SUCCESS else ""
        lines.append(f"- {item.source_id}: {item.status.value.upper()}{suffix}")
    return "\n".join(lines)


def render_batch_report_markdown(result: BatchRunResult) -> str:
    lines = [
        "# Rapport TPStudio — Lot Snell-Descartes", "", "## Synthèse", "",
        f"- Copies : {len(result.results)}", f"- Succès : {result.success_count}",
        f"- Échecs : {result.failed_count}", f"- Ignorées : {result.skipped_count}",
        f"- Annotations : {result.total_annotation_count}",
        f"- Revue humaine confirmée : {result.human_review_count}", "", "## Résultats par copie", "",
        "| Source | Statut | Notebook | HTML | Annotations | Revue humaine | Limites |",
        "|---|---|---|---|---:|---|---|",
    ]
    for item in result.results:
        notebook = item.notebook_path.name if item.notebook_path else "—"
        html = item.html_path.name if item.html_path else "—"
        lines.append(f"| {item.source_id} | {item.status.value} | {notebook} | {html} | {item.annotation_count} | {_human_review_label(item.requires_human_review)} | {len(item.limitations)} |")
    lines += ["", "## Échecs", ""]
    for item in result.failed_results:
        lines.append(f"- `{item.source_id}` — {item.error_type}: {item.error_message}")
    return "\n".join(lines) + "\n"


def write_batch_report(markdown: str, output_path: Path, *, overwrite: bool = False) -> Path:
    if not isinstance(output_path, Path) or not isinstance(markdown, str):
        raise TypeError("Le rapport et son chemin sont invalides.")
    if output_path.exists() and not overwrite:
        raise FileExistsError("Le rapport existe déjà.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return output_path
