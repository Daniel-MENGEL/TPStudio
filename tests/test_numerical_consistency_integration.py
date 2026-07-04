from __future__ import annotations

from pathlib import Path

import nbformat

from tpstudio.copy_feedback import create_feedback_notebook
from tpstudio.feedback_report import export_feedback_report


def _stream(text: str):
    return nbformat.v4.new_output(
        output_type="stream",
        name="stdout",
        text=text,
    )


def _write(path: Path, notebook) -> None:
    nbformat.write(notebook, path)


def test_feedback_pipeline_reports_numerical_inconsistency(
    tmp_path: Path,
) -> None:
    model = tmp_path / "model.ipynb"
    copy = tmp_path / "copy.ipynb"
    corrected = tmp_path / "copy-correction.ipynb"
    report = tmp_path / "copy-correction.md"

    _write(
        model,
        nbformat.v4.new_notebook(
            cells=[
                nbformat.v4.new_markdown_cell(
                    "# Première méthode"
                ),
                nbformat.v4.new_code_cell(
                    "n = 1 / np.sin(il)"
                ),
            ]
        ),
    )

    _write(
        copy,
        nbformat.v4.new_notebook(
            cells=[
                nbformat.v4.new_markdown_cell(
                    "# Première méthode"
                ),
                nbformat.v4.new_code_cell(
                    "n = 2 / np.sin(il)",
                    outputs=[
                        _stream(
                            "Meilleur estimateur : n= 2.99\n"
                        )
                    ],
                ),
                nbformat.v4.new_markdown_cell(
                    "**Réponse :** On obtient un indice proche de 1,49."
                ),
            ]
        ),
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

    assert "Retour TPStudio — cohérence numérique" in corrected_text
    assert "Cohérence des résultats numériques" in report_text
    assert "Résultats numériques incompatibles : **1**" in report_text
    assert "2.99" in report_text
    assert "1.49" in report_text
