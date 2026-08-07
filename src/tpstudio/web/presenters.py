"""Pure, privacy-conscious presentation helpers."""

from __future__ import annotations

from dataclasses import dataclass

from tpstudio.batch import BatchPlan


@dataclass(frozen=True, slots=True)
class BatchPlanRow:
    source_id: str
    original_filename: str
    notebook_output_name: str
    html_output_name: str


def batch_plan_rows(plan: BatchPlan) -> tuple[BatchPlanRow, ...]:
    return tuple(
        BatchPlanRow(source.source_id, source.display_name or source.path.name, output.notebook_path.name, output.html_path.name)
        for source, output in zip(plan.sources, plan.planned_outputs)
    )


def has_output_name_collision(plan: BatchPlan) -> bool:
    source_names = [source.display_name or source.path.name for source in plan.sources]
    return len(source_names) != len(set(source_names))
