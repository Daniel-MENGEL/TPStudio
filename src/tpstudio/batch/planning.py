"""Deterministic preflight planning for small batches."""

from __future__ import annotations

import re
from pathlib import Path

from tpstudio.export import default_export_names

from .model import BatchCopySource, BatchOptions, BatchPlan, PlannedBatchOutput


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _same(first: Path, second: Path) -> bool:
    return first.resolve() == second.resolve()


def _validate_source_id(source_id: str) -> None:
    if not _SAFE_ID.fullmatch(source_id) or ".." in source_id:
        raise ValueError("source_id doit être un identifiant local sûr sans séparateur.")


def resolve_batch_output_names(
    sources: tuple[BatchCopySource, ...],
    output_dir: Path,
) -> tuple[PlannedBatchOutput, ...]:
    simple = [default_export_names((item.output_stem or item.path.name)) for item in sources]
    collision_names = set()
    for names in simple:
        collision_names.update(names)
    counts = {name: sum(names[index] == name for names in simple for index in (0, 1)) for name in collision_names}
    planned = []
    for item, names in zip(sources, simple):
        if any(counts[name] > 1 for name in names):
            notebook_name = f"{item.source_id}-{names[0]}"
            html_name = f"{item.source_id}-{names[1]}"
        else:
            notebook_name, html_name = names
        planned.append(PlannedBatchOutput(item.source_id, output_dir / notebook_name, output_dir / html_name))
    return tuple(planned)


def build_batch_plan(
    sources: tuple[BatchCopySource, ...],
    output_dir: Path,
    options: BatchOptions | None = None,
) -> BatchPlan:
    sources = tuple(sources)
    if not sources:
        raise ValueError("Un lot exige au moins une source explicite.")
    if not isinstance(output_dir, Path):
        raise TypeError("output_dir doit être un pathlib.Path.")
    options = BatchOptions() if options is None else options
    if type(options) is not BatchOptions:
        raise TypeError("Les options de lot sont invalides.")
    if len({item.source_id for item in sources}) != len(sources):
        raise ValueError("Les source_id doivent être uniques.")
    for item in sources:
        _validate_source_id(item.source_id)
        if not item.path.exists() or not item.path.is_file():
            raise FileNotFoundError(f"Source indisponible : {item.source_id}")
    canonical_sources = [item.path.resolve() for item in sources]
    if len(set(canonical_sources)) != len(canonical_sources):
        raise ValueError("Les chemins source doivent être uniques.")
    output_dir = output_dir.resolve()
    planned = resolve_batch_output_names(sources, output_dir)
    destinations = [path for item in planned for path in (item.notebook_path, item.html_path)]
    if len({path.resolve() for path in destinations}) != len(destinations):
        raise ValueError("Les sorties du lot entrent en collision.")
    for source in sources:
        if any(_same(destination, source.path) for destination in destinations):
            raise ValueError("Une sortie du lot désigne une source.")
    return BatchPlan(sources, output_dir, options, planned)
