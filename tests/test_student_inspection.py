from __future__ import annotations

import json
from pathlib import Path

from tpstudio.student_inspection import (
    format_student_notebook_report,
    inspect_student_notebook,
)


def _write_notebook(path: Path, cells: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "cells": cells,
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_student_inspection_counts_response_cells(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"
    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Partie 1\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\nLa valeur mesurée est correcte.\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
        ],
    )

    diagnostic = inspect_student_notebook(notebook)

    assert diagnostic.total_cells == 3
    assert diagnostic.markdown_cells == 3
    assert diagnostic.response_cells == 2
    assert diagnostic.filled_response_cells == 1
    assert diagnostic.empty_response_cells == 1
    assert diagnostic.headings == 1


def test_student_inspection_counts_code_execution_state(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"
    _write_notebook(
        notebook,
        [
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [{"output_type": "stream", "text": ["ok\n"]}],
                "source": ["print('ok')\n"],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["x = 1\n"],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 2,
                "outputs": [{"output_type": "error", "ename": "ValueError"}],
                "source": ["raise ValueError()\n"],
            },
        ],
    )

    diagnostic = inspect_student_notebook(notebook)

    assert diagnostic.code_cells == 3
    assert diagnostic.code_cells_with_outputs == 2
    assert diagnostic.code_cells_without_outputs == 1
    assert diagnostic.code_cells_not_executed == 1
    assert diagnostic.code_cells_with_errors == 1


def test_student_inspection_formats_report(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"
    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\nÀ compléter\n"]},
        ],
    )

    diagnostic = inspect_student_notebook(notebook)
    report = format_student_notebook_report(diagnostic)

    assert "Inspection de copie" in report
    assert "réponses vides ou à compléter : 1" in report
    assert "Cellules à vérifier" in report
    assert "cellule 1 — réponse vide ou à compléter" in report
    assert "Points globaux à vérifier" in report
    assert "Corrigeabilité automatique" in report


def test_student_inspection_lists_cell_issues(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"
    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** Oui\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["print('resultat')\n"],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 2,
                "outputs": [{"output_type": "error", "ename": "ValueError"}],
                "source": ["raise ValueError()\n"],
            },
        ],
    )

    diagnostic = inspect_student_notebook(notebook)

    kinds = [issue.kind for issue in diagnostic.issues]
    assert "empty_response" in kinds
    assert "short_response" in kinds
    assert "not_executed" in kinds
    assert "execution_error" in kinds

    report = format_student_notebook_report(diagnostic)
    assert "cellule 1 — réponse vide ou à compléter" in report
    assert "cellule 2 — réponse très courte à relire" in report
    assert "cellule 3 — cellule de code non exécutée" in report
    assert "cellule 4 — erreur d'exécution présente" in report


def test_student_inspection_lists_global_issues_separately(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"
    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Résultats\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [],
                "source": ["x = 1\n"],
            },
        ],
    )

    diagnostic = inspect_student_notebook(notebook)

    assert diagnostic.issues == []
    global_kinds = [issue.kind for issue in diagnostic.global_issues]
    assert "no_response_zones" in global_kinds
    assert "difficult_auto_correction" in global_kinds

    report = format_student_notebook_report(diagnostic)
    assert "✓ aucune cellule problématique évidente détectée" in report
    assert "⚠ Points globaux à vérifier" in report
    assert "aucune zone « Réponse : » détectée" in report
    assert "correction automatique difficile avec ce notebook" in report


def test_student_inspection_ignores_empty_code_cells(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"
    _write_notebook(
        notebook,
        [
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["\n"],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["# brouillon laissé vide\n"],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["print('à exécuter')\n"],
            },
        ],
    )

    diagnostic = inspect_student_notebook(notebook)

    assert diagnostic.code_cells == 3
    assert diagnostic.empty_code_cells == 2
    assert diagnostic.code_cells_not_executed == 1
    assert [issue.cell_number for issue in diagnostic.issues if issue.kind == "not_executed"] == [3]

    report = format_student_notebook_report(diagnostic)
    assert "cellules de code vides ignorées : 2" in report
    assert "cellule 1 — cellule de code non exécutée" not in report
    assert "cellule 2 — cellule de code non exécutée" not in report
    assert "cellule 3 — cellule de code non exécutée" in report


def test_student_inspection_estimates_correction_readiness(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"
    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Mesure\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** La mesure est cohérente.\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["### Résultat — mesure\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["### Interprétation\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["### Checklist finale\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [{"output_type": "stream", "text": ["ok\n"]}],
                "source": ["print('ok')\n"],
            },
        ],
    )

    diagnostic = inspect_student_notebook(notebook)

    assert diagnostic.result_cells == 1
    assert diagnostic.interpretation_cells == 1
    assert diagnostic.checklist_cells == 1
    assert diagnostic.correction_readiness is not None
    assert diagnostic.correction_readiness.level == "très bonne"

    report = format_student_notebook_report(diagnostic)
    assert "🧪 Corrigeabilité automatique" in report
    assert "niveau : très bonne" in report
    assert "zones « Réponse : » présentes" in report


def test_student_inspection_distinguishes_code_to_complete(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"
    _write_notebook(
        notebook,
        [
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["x = ?\n"],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 8,
                "outputs": [{"output_type": "stream", "text": ["?\n"]}],
                "source": ["print(?)\n"],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["import numpy as np\n"],
            },
        ],
    )

    diagnostic = inspect_student_notebook(notebook)

    assert diagnostic.code_cells_to_complete == 2
    assert diagnostic.code_cells_not_executed == 2

    issues = {issue.cell_number: issue for issue in diagnostic.issues}
    assert issues[1].kind == "code_to_complete_not_executed"
    assert issues[1].message == "cellule à compléter et à exécuter"
    assert issues[2].kind == "code_to_complete"
    assert issues[2].message == "cellule exécutée avec du code à compléter"
    assert issues[3].kind == "not_executed"
    assert issues[3].message == "cellule de code non exécutée"

    report = format_student_notebook_report(diagnostic)
    assert "cellule 1 — cellule à compléter et à exécuter" in report
    assert "cellule 2 — cellule exécutée avec du code à compléter" in report
    assert "cellule 3 — cellule de code non exécutée" in report
    assert "cellules à compléter : 2" in report
