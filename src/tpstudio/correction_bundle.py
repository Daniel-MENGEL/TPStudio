from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import tempfile

from tpstudio.copy_feedback import create_feedback_notebook
from tpstudio.feedback_report import export_feedback_report
from tpstudio.notebook_execution import (
    NotebookExecutionResult,
    execute_notebook_copy,
)


@dataclass(frozen=True)
class CorrectionBundlePaths:
    notebook: Path
    markdown_report: Path
    execution: NotebookExecutionResult | None = None


def correct_copy(
    model_path: str | Path,
    copy_path: str | Path,
    *,
    output_dir: str | Path,
    overwrite: bool = False,
    execute_first: bool = False,
    cell_timeout: int = 60,
    kernel_name: str | None = None,
    continue_on_error: bool = False,
) -> CorrectionBundlePaths:
    """Create a corrected notebook and report without touching the original."""

    model = Path(model_path)
    source = Path(copy_path)
    destination = Path(output_dir)

    _validate_notebook_input(model, "modèle")
    _validate_notebook_input(source, "copie")

    destination.mkdir(parents=True, exist_ok=True)

    notebook_output = destination / f"{source.stem}-correction.ipynb"
    report_output = destination / f"{source.stem}-correction.md"

    if not overwrite:
        existing = [
            path
            for path in (notebook_output, report_output)
            if path.exists()
        ]
        if existing:
            names = ", ".join(path.name for path in existing)
            raise FileExistsError(
                f"Sortie déjà existante : {names}. "
                "Utilise --overwrite pour la remplacer."
            )

    execution_result: NotebookExecutionResult | None = None

    with tempfile.TemporaryDirectory(
        dir=destination,
        prefix=".tpstudio-correction-",
    ) as temporary_directory:
        temporary = Path(temporary_directory)
        temporary_notebook = temporary / notebook_output.name
        temporary_report = temporary / report_output.name

        working_copy = source

        if execute_first:
            executed_copy = temporary / f"{source.stem}-executed.ipynb"
            execution_result = execute_notebook_copy(
                source,
                executed_copy,
                cell_timeout=cell_timeout,
                kernel_name=kernel_name,
                continue_on_error=continue_on_error,
            )
            working_copy = executed_copy

        create_feedback_notebook(
            model,
            working_copy,
            temporary_notebook,
        )
        export_feedback_report(
            model,
            working_copy,
            temporary_report,
        )

        if execution_result is not None:
            _append_execution_summary(
                temporary_report,
                execution_result,
            )

        temporary_notebook.replace(notebook_output)
        temporary_report.replace(report_output)

    if execution_result is not None:
        execution_result = replace(
            execution_result,
            output=notebook_output,
        )

    return CorrectionBundlePaths(
        notebook=notebook_output,
        markdown_report=report_output,
        execution=execution_result,
    )


def _append_execution_summary(
    report_path: Path,
    result: NotebookExecutionResult,
) -> None:
    text = report_path.read_text(encoding="utf-8")

    if "## Exécution préalable" in text:
        return

    if result.success:
        status = "succès"
    elif result.completed:
        status = "terminée avec erreurs"
    else:
        status = "interrompue avec erreur"

    lines = [
        "",
        "",
        "## Exécution préalable",
        "",
        f"- Statut : {status}",
        (
            "- Kernel déclaré par le notebook : "
            f"{result.declared_kernel or 'aucun'}"
        ),
        f"- Kernel utilisé : {result.used_kernel or 'inconnu'}",
        (
            "- Fallback automatique : "
            + ("oui" if result.fallback_used else "non")
        ),
        (
            "- Cellules code tentées : "
            f"{result.attempted_code_cells}/{result.total_code_cells}"
        ),
        f"- Erreurs détectées : {result.error_count}",
    ]

    if result.failed_cell_index is not None:
        lines.append(
            "- Première cellule en erreur : "
            f"{result.failed_cell_index + 1}"
        )

    if result.error_type:
        lines.append(f"- Type d'erreur : {result.error_type}")

    if result.error_message:
        lines.append(f"- Message : {result.error_message}")

    report_path.write_text(
        text.rstrip() + "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _validate_notebook_input(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label.capitalize()} introuvable : {path}")

    if not path.is_file():
        raise ValueError(f"{label.capitalize()} invalide : {path}")

    if path.suffix.lower() != ".ipynb":
        raise ValueError(
            f"{label.capitalize()} attendu au format .ipynb : {path}"
        )
