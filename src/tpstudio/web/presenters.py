"""Pure, privacy-conscious presentation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from tpstudio.batch import BatchPlan


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
