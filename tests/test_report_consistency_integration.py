from __future__ import annotations

from pathlib import Path

import nbformat

from tpstudio.feedback_report import export_feedback_report


def _stream(text: str):
    return nbformat.v4.new_output(
        output_type="stream",
        name="stdout",
        text=text,
    )


def _write(path: Path, notebook) -> None:
    nbformat.write(notebook, path)


def test_full_report_summary_reflects_scientific_problems(
    tmp_path: Path,
) -> None:
    model = tmp_path / "model.ipynb"
    copy = tmp_path / "copy.ipynb"
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

    export_feedback_report(
        model,
        copy,
        report,
    )

    text = report.read_text(encoding="utf-8")

    assert (
        "Corrigeabilité globale : **à reprendre**"
        in text
    )
    assert (
        "Raison principale : **erreurs de formule et "
        "incohérences numériques détectées**"
        in text
    )
    assert (
        "Points scientifiques prioritaires : **2** "
        "(1 formule(s), 1 résultat(s) numérique(s))"
        in text
    )
    assert (
        "Corrigeabilité technique : **bonne base**"
        in text
    )
