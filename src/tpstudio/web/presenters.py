"""Pure, privacy-conscious presentation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from pathlib import Path

from tpstudio.batch import BatchPlan
from tpstudio.batch import BatchCopyStatus, BatchRunResult


@dataclass(frozen=True, slots=True)
class BatchPlanRow:
    copy_label: str
    source_id: str
    original_filename: str
    students_display: str
    identity_status: str
    identity_source: str
    notebook_output_name: str
    html_output_name: str


def batch_plan_rows(plan: BatchPlan, identities: Mapping[str, object] | None = None) -> tuple[BatchPlanRow, ...]:
    identities = identities or {}
    labels = {"confirmed": "Confirmée", "to_review": "À vérifier", "missing": "Non renseignée"}
    return tuple(
        BatchPlanRow(
            f"Copie {index}", source.source_id, source.display_name or source.path.name,
            " · ".join(student.display_name for student in getattr(identities.get(source.source_id), "students", ())) or "—",
            labels.get(getattr(getattr(identities.get(source.source_id), "status", None), "value", ""), "Non renseignée"),
            {"notebook": "Notebook", "filename": "Nom du fichier"}.get(getattr(getattr(identities.get(source.source_id), "source", None), "value", ""), "—"),
            output.notebook_path.name, output.html_path.name,
        )
        for index, (source, output) in enumerate(zip(plan.sources, plan.planned_outputs), 1)
    )


def has_output_name_collision(plan: BatchPlan) -> bool:
    source_names = [source.display_name or source.path.name for source in plan.sources]
    return len(source_names) != len(set(source_names))


@dataclass(frozen=True, slots=True)
class BatchRunRow:
    copy_label: str
    source_id: str
    students_display: str
    status: str
    notebook_output_name: str
    html_output_name: str
    annotation_count: int
    human_review: str
    limitations: str
    error: str
    problem: str


def _review_label(value: bool | None) -> str:
    return "oui" if value is True else "non" if value is False else "indéterminée"


def batch_run_rows(result: BatchRunResult, selected_copies=()) -> tuple[BatchRunRow, ...]:
    identities = {item.source_id: item.identity for item in selected_copies}
    labels = {BatchCopyStatus.SUCCESS: "Réussie", BatchCopyStatus.FAILED: "Échec", BatchCopyStatus.SKIPPED: "Ignorée"}
    rows = []
    for index, item in enumerate(result.results, 1):
        identity = identities.get(item.source_id)
        students = " · ".join(student.display_name for student in getattr(identity, "students", ())) or "—"
        rows.append(BatchRunRow(
            f"Copie {index}", item.source_id, students, labels[item.status],
            item.notebook_path.name if item.notebook_path else "—",
            item.html_path.name if item.html_path else "—",
            item.annotation_count, _review_label(item.requires_human_review),
            " ; ".join(item.limitations) or "—", item.error_message or "",
            item.error_message or "—" if item.status is not BatchCopyStatus.SUCCESS else "—",
        ))
    return tuple(rows)


def artifact_download_info(item, output_dir: Path, kind: str) -> tuple[str, str, Path]:
    if kind not in {"notebook", "html"}:
        raise ValueError("Type d'artefact invalide.")
    path = item.notebook_path if kind == "notebook" else item.html_path
    if not isinstance(path, Path) or not isinstance(output_dir, Path):
        raise ValueError("Artefact invalide.")
    resolved_output = output_dir.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_output)
    except ValueError as exc:
        raise ValueError("Artefact hors du dossier de sortie.") from exc
    if not resolved_path.is_file():
        raise FileNotFoundError("Artefact indisponible.")
    return path.name, "application/x-ipynb+json" if kind == "notebook" else "text/html", path
