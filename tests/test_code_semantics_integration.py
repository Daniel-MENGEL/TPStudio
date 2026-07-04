from __future__ import annotations

from pathlib import Path

import nbformat

from tpstudio.copy_feedback import create_feedback_notebook
from tpstudio.feedback_report import export_feedback_report


def _write_notebook(path: Path, cells: list) -> None:
    notebook = nbformat.v4.new_notebook(cells=cells)
    nbformat.write(notebook, path)


def test_feedback_pipeline_reports_semantic_code_differences(
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
                "## Première méthode"
            ),
            nbformat.v4.new_code_cell(
                "n = 1 / np.sin(il)"
            ),
            nbformat.v4.new_markdown_cell(
                "## Dernière méthode"
            ),
            nbformat.v4.new_code_cell(
                "n = sini1 / sini2"
            ),
        ],
    )

    _write_notebook(
        copy,
        [
            nbformat.v4.new_markdown_cell(
                "## Première méthode"
            ),
            nbformat.v4.new_code_cell(
                "n = 2 / np.sin(il)"
            ),
            nbformat.v4.new_markdown_cell(
                "## Dernière méthode"
            ),
            nbformat.v4.new_code_cell(
                "n = sini2 / sini1"
            ),
        ],
    )

    create_feedback_notebook(
        model,
        copy,
        corrected,
    )
    export_feedback_report(
        model,
        copy,
        report,
    )

    corrected_nb = nbformat.read(
        corrected,
        as_version=4,
    )
    corrected_text = "\n".join(
        str(cell.source)
        for cell in corrected_nb.cells
    )
    report_text = report.read_text(
        encoding="utf-8",
    )

    assert corrected_text.count(
        "Retour TPStudio — code à vérifier"
    ) == 2

    assert (
        "Diagnostic sémantique du code"
        in report_text
    )
    assert (
        "Écarts sémantiques à vérifier : **2**"
        in report_text
    )
    assert "2 / np.sin(il)" in report_text
    assert "sini2 / sini1" in report_text
