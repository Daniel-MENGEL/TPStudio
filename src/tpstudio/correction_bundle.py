from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile

from tpstudio.copy_feedback import create_feedback_notebook
from tpstudio.feedback_report import export_feedback_report


@dataclass(frozen=True)
class CorrectionBundlePaths:
    notebook: Path
    markdown_report: Path


def correct_copy(
    model_path: str | Path,
    copy_path: str | Path,
    *,
    output_dir: str | Path,
    overwrite: bool = False,
) -> CorrectionBundlePaths:
    """Create a corrected notebook and its Markdown report without touching the original."""

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

    # Travail transactionnel dans un dossier temporaire :
    # aucun fichier final n'est publié tant que les deux sorties ne sont pas prêtes.
    with tempfile.TemporaryDirectory(
        dir=destination,
        prefix=".tpstudio-correction-",
    ) as temporary_directory:
        temporary = Path(temporary_directory)
        temporary_notebook = temporary / notebook_output.name
        temporary_report = temporary / report_output.name

        create_feedback_notebook(
            model,
            source,
            temporary_notebook,
        )
        export_feedback_report(
            model,
            source,
            temporary_report,
        )

        temporary_notebook.replace(notebook_output)
        temporary_report.replace(report_output)

    return CorrectionBundlePaths(
        notebook=notebook_output,
        markdown_report=report_output,
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
