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
