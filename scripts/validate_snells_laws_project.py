"""Validate the Snell-Descartes project against explicitly supplied notebooks."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import nbformat

from tpstudio.notebooks import (
    NotebookBindingResolutionStatus,
    resolve_notebook_bindings,
)
from tpstudio.projects import snells_laws_teacher_project


@dataclass(frozen=True, slots=True)
class SnellsLawsNotebookValidation:
    statement_path: Path
    cell_count: int
    resolved_binding_ids: tuple[str, ...]
    missing_binding_ids: tuple[str, ...]
    ambiguous_binding_ids: tuple[str, ...]
    covered_production_ids: tuple[str, ...]
    correction_path: Path | None = None
    correction_cell_count: int | None = None

    @property
    def all_resolved(self) -> bool:
        return not self.missing_binding_ids and not self.ambiguous_binding_ids


def validate_snells_laws_notebooks(
    statement_path: str | Path,
    correction_path: str | Path | None = None,
) -> SnellsLawsNotebookValidation:
    """Load notebooks as data and resolve configured statement bindings."""

    statement = Path(statement_path)
    notebook = nbformat.read(statement, as_version=4)
    project = snells_laws_teacher_project()
    resolutions = resolve_notebook_bindings(notebook, project.notebook_binding_plan)
    missing_statuses = {
        NotebookBindingResolutionStatus.CELL_NOT_FOUND,
        NotebookBindingResolutionStatus.TEXT_MARKER_NOT_FOUND,
    }
    ambiguous_statuses = {
        NotebookBindingResolutionStatus.CELL_AMBIGUOUS,
        NotebookBindingResolutionStatus.TEXT_MARKER_AMBIGUOUS,
    }
    correction = Path(correction_path) if correction_path is not None else None
    correction_cells = None
    if correction is not None:
        correction_notebook = nbformat.read(correction, as_version=4)
        correction_cells = len(correction_notebook.cells)
    resolved = tuple(item.binding_id for item in resolutions if item.resolved)
    missing = tuple(
        item.binding_id for item in resolutions if item.status in missing_statuses
    )
    ambiguous = tuple(
        item.binding_id for item in resolutions if item.status in ambiguous_statuses
    )
    covered = tuple(
        dict.fromkeys(item.production_id for item in resolutions if item.resolved)
    )
    return SnellsLawsNotebookValidation(
        statement,
        len(notebook.cells),
        resolved,
        missing,
        ambiguous,
        covered,
        correction,
        correction_cells,
    )


def format_snells_laws_validation_report(
    validation: SnellsLawsNotebookValidation,
) -> str:
    lines = [
        f"Énoncé analysé : {validation.statement_path}",
        f"Cellules : {validation.cell_count}",
        f"Bindings résolus : {len(validation.resolved_binding_ids)}",
        f"Bindings absents : {len(validation.missing_binding_ids)}",
        f"Bindings ambigus : {len(validation.ambiguous_binding_ids)}",
        f"Productions couvertes : {len(validation.covered_production_ids)}",
    ]
    if validation.missing_binding_ids:
        lines.append("Absents : " + ", ".join(validation.missing_binding_ids))
    if validation.ambiguous_binding_ids:
        lines.append("Ambigus : " + ", ".join(validation.ambiguous_binding_ids))
    lines.append("Couvertes : " + ", ".join(validation.covered_production_ids))
    if validation.correction_path is not None:
        lines.append(f"Corrigé lu sans exécution : {validation.correction_path}")
        lines.append(f"Cellules du corrigé : {validation.correction_cell_count}")
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Valide la configuration interne Snell-Descartes sans exécuter de code."
    )
    parser.add_argument("statement", type=Path)
    parser.add_argument("--correction", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    validation = validate_snells_laws_notebooks(args.statement, args.correction)
    print(format_snells_laws_validation_report(validation))
    return 0 if validation.all_resolved else 1


if __name__ == "__main__":
    raise SystemExit(main())
