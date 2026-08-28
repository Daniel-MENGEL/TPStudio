from __future__ import annotations

from pathlib import Path

import nbformat

from tpstudio.copy_feedback import create_feedback_notebook
from tpstudio.feedback_report import export_feedback_report


def _write_notebook(path: Path, cells: list) -> None:
    notebook = nbformat.v4.new_notebook(cells=cells)
    nbformat.write(notebook, path)


def test_feedback_pipeline_covers_fragile_protocol_without_response_marker(
    tmp_path: Path,
) -> None:
    model = tmp_path / "model.ipynb"
    copy = tmp_path / "copy.ipynb"
    corrected = tmp_path / "copy-correction.ipynb"
    report = tmp_path / "copy-correction.md"

    _write_notebook(
        model,
        [
            nbformat.v4.new_markdown_cell(
                "## Protocole\n\n"
                "Placer le disque, aligner le laser, relever les angles "
                "d'incidence et de réfraction puis reporter les mesures."
            )
        ],
    )
    _write_notebook(
        copy,
        [
            nbformat.v4.new_markdown_cell(
                "## Protocole\n\n"
                "On utilise le matériel qui nous a été fourni."
            )
        ],
    )

    create_feedback_notebook(model, copy, corrected)
    export_feedback_report(model, copy, report)

    corrected_nb = nbformat.read(corrected, as_version=4)
    corrected_text = "\n".join(
        str(cell.source)
        for cell in corrected_nb.cells
    )
    report_text = report.read_text(encoding="utf-8")

    assert "### Protocole" in corrected_text
    assert "Retour TPStudio — Protocole" not in corrected_text
    assert "Diagnostic des sections pédagogiques" in report_text
    assert "Protocole" in report_text
    assert "fragile" in report_text
