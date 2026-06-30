import json
from pathlib import Path

from tpstudio.improver import improve_notebook


def _write_minimal_notebook(path: Path, title: str = "TP test") -> None:
    data = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [f"# {title}\n"],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["## Mesure principale\n", "\n", "### Exploitation\n"],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": ["x = 1\n"],
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _notebook_text(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in data.get("cells", [])
    )


def test_improve_adds_evaluation_grid_when_rapport_is_active(tmp_path: Path) -> None:
    notebook = tmp_path / "TP.ipynb"
    tex = tmp_path / "TP.tex"

    _write_minimal_notebook(notebook)
    tex.write_text("\\rapport\n", encoding="utf-8")

    output = improve_notebook(tmp_path)
    text = _notebook_text(output)

    assert "Évaluation par compétences" in text
    assert "Checklist de fin de TP" not in text


def test_improve_adds_checklist_when_rapport_is_commented(tmp_path: Path) -> None:
    notebook = tmp_path / "TP.ipynb"
    tex = tmp_path / "TP.tex"

    _write_minimal_notebook(notebook)
    tex.write_text("%\\rapport\n", encoding="utf-8")

    output = improve_notebook(tmp_path)
    text = _notebook_text(output)

    assert "Checklist de fin de TP" in text
    assert "Évaluation par compétences" not in text


def test_improve_adds_checklist_when_rapport_is_absent(tmp_path: Path) -> None:
    notebook = tmp_path / "TP.ipynb"
    tex = tmp_path / "TP.tex"

    _write_minimal_notebook(notebook)
    tex.write_text("\\section{TP sans rapport}\n", encoding="utf-8")

    output = improve_notebook(tmp_path)
    text = _notebook_text(output)

    assert "Checklist de fin de TP" in text
    assert "Évaluation par compétences" not in text


def test_improve_does_not_modify_original_notebook(tmp_path: Path) -> None:
    notebook = tmp_path / "TP.ipynb"
    tex = tmp_path / "TP.tex"

    _write_minimal_notebook(notebook)
    tex.write_text("\\rapport\n", encoding="utf-8")
    original = notebook.read_text(encoding="utf-8")

    output = improve_notebook(tmp_path)

    assert output != notebook
    assert notebook.read_text(encoding="utf-8") == original


def test_improve_ignores_already_improved_notebooks_as_source(tmp_path: Path) -> None:
    source = tmp_path / "TP.ipynb"
    improved = tmp_path / "TP-ameliore.ipynb"
    tex = tmp_path / "TP.tex"

    _write_minimal_notebook(source, title="Notebook source")
    _write_minimal_notebook(improved, title="Notebook déjà amélioré")
    tex.write_text("\\rapport\n", encoding="utf-8")

    output = improve_notebook(tmp_path)
    text = _notebook_text(output)

    assert output.name == "TP-ameliore-2.ipynb"
    assert "# Notebook source" in text
    assert "# Notebook déjà amélioré" not in text


def test_improve_creates_notebook_when_no_source_notebook_exists(tmp_path: Path) -> None:
    tex = tmp_path / "TP sans notebook.tex"
    tex.write_text(
        "\\section{Première partie}\n"
        "\\section{Deuxième partie}\n",
        encoding="utf-8",
    )

    output = improve_notebook(tmp_path)
    text = _notebook_text(output)

    assert output.suffix == ".ipynb"
    assert output.exists()
    assert "Première partie" in text
    assert "Deuxième partie" in text


def test_latex_only_output_name_normalizes_decomposed_accents(tmp_path: Path) -> None:
    tex = tmp_path / "Oscillateur électrique amorti.tex"
    tex.write_text("\\section{Circuit}\n", encoding="utf-8")

    output = improve_notebook(tmp_path)

    assert output.name == "Oscillateur-electrique-amorti.ipynb"


def test_result_cell_for_wavelength_stays_before_indirect_measurement(tmp_path: Path) -> None:
    notebook = tmp_path / "Ondes ultrasonores.ipynb"
    notebook.write_text(
        json.dumps(
            {
                "cells": [
                    {"cell_type": "markdown", "metadata": {}, "source": ["## Onde progressive\n", "\n", "### Mesure de la longueur d'onde\n"]},
                    {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": ["print('lambda')\n"]},
                    {"cell_type": "markdown", "metadata": {}, "source": ["🧠 Commentez :\n"]},
                    {"cell_type": "markdown", "metadata": {}, "source": ["### Mesure indirecte $c_i$\n"]},
                    {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": ["print('ci')\n"]},
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tex = tmp_path / "Ondes ultrasonores.tex"
    tex.write_text("\\rapport\n", encoding="utf-8")

    output = improve_notebook(tmp_path)
    text = _notebook_text(output)

    result_index = text.index("Résultat — Mesure de la longueur d'onde")
    indirect_index = text.index("Mesure indirecte")

    assert result_index < indirect_index


def test_generic_comment_cells_are_removed_from_improved_notebook(tmp_path: Path) -> None:
    notebook = tmp_path / "TP.ipynb"
    notebook.write_text(
        json.dumps(
            {
                "cells": [
                    {"cell_type": "markdown", "metadata": {}, "source": ["## Mesure de la longueur d'onde\n"]},
                    {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": ["print('lambda')\n"]},
                    {"cell_type": "markdown", "metadata": {}, "source": ["🧠 Commentez :\n"]},
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tex = tmp_path / "TP.tex"
    tex.write_text("\\rapport\n", encoding="utf-8")

    output = improve_notebook(tmp_path)
    text = _notebook_text(output)

    assert "🧠 Commentez" not in text


def test_result_cell_stays_before_conclusion_bilan(tmp_path: Path) -> None:
    notebook = tmp_path / "Lois de Snell Descartes.ipynb"
    notebook.write_text(
        json.dumps(
            {
                "cells": [
                    {"cell_type": "markdown", "metadata": {}, "source": ["## Vérification de la loi de la réfraction et dernière méthode de mesure de l’indice\n"]},
                    {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": ["print('verification')\n"]},
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tex = tmp_path / "Lois de Snell Descartes.tex"
    tex.write_text("\\rapport\n", encoding="utf-8")

    output = improve_notebook(tmp_path)
    text = _notebook_text(output)

    result_index = text.index("Résultat — Vérification de la loi de la réfraction")
    conclusion_index = text.index("Conclusion / bilan")

    assert result_index < conclusion_index


def test_comparison_is_placed_after_following_result_cell(tmp_path: Path) -> None:
    notebook = tmp_path / "Ondes stationnaires.ipynb"
    notebook.write_text(
        json.dumps(
            {
                "cells": [
                    {"cell_type": "markdown", "metadata": {}, "source": ["## Ondes sonores stationnaires\n"]},
                    {"cell_type": "markdown", "metadata": {}, "source": ["### Comparaison des résultats obtenus\n"]},
                    {"cell_type": "markdown", "metadata": {}, "source": ["## Mesure de la longueur d'onde et de la célérité du son\n"]},
                    {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": ["print('lambda et c')\n"]},
                    {"cell_type": "markdown", "metadata": {}, "source": ["### Résultat — Mesure de la longueur d'onde et de la célérité du son\n"]},
                    {"cell_type": "markdown", "metadata": {}, "source": ["### Conclusion / bilan\n"]},
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tex = tmp_path / "Ondes stationnaires.tex"
    tex.write_text("\\rapport\n", encoding="utf-8")

    output = improve_notebook(tmp_path)
    text = _notebook_text(output)

    result_index = text.index("Résultat — Mesure de la longueur d'onde et de la célérité")
    comparison_index = text.index("Comparaison des résultats obtenus")
    conclusion_index = text.index("Conclusion / bilan")

    assert result_index < comparison_index < conclusion_index
