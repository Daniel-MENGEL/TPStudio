from __future__ import annotations

from pathlib import Path

import nbformat

from tpstudio.copy_feedback import create_feedback_notebook
from tpstudio.feedback_report import export_feedback_report


def _write_notebook(path: Path, source: str) -> None:
    notebook = nbformat.v4.new_notebook(
        cells=[nbformat.v4.new_markdown_cell(source)]
    )
    nbformat.write(notebook, path)


def test_a61a_keeps_automatic_feedback_notebook_output(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        "## Protocole\n\n"
        "Placer le disque, aligner le laser et relever les angles.",
    )
    _write_notebook(
        copy,
        "## Protocole\n\n"
        "On utilise le matériel qui nous a été fourni.",
    )

    created = create_feedback_notebook(model, copy)

    assert created.exists()

    notebook = nbformat.read(created, as_version=4)
    text = "\n".join(str(cell.source) for cell in notebook.cells)

    assert "### Protocole" in text
    assert "Retour TPStudio — Protocole" not in text


def test_a61a_keeps_automatic_feedback_report_output(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        "## Protocole\n\n"
        "Placer le disque, aligner le laser et relever les angles.",
    )
    _write_notebook(
        copy,
        "## Protocole\n\n"
        "On utilise le matériel qui nous a été fourni.",
    )

    created = export_feedback_report(model, copy)

    assert created.exists()

    text = created.read_text(encoding="utf-8")

    assert "Diagnostic des sections pédagogiques" in text
    assert "Protocole" in text
