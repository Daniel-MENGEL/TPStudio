from __future__ import annotations

import json
from pathlib import Path

from tpstudio.copy_comparison import (
    compare_copy_to_model,
    format_copy_comparison_report,
    student_feedback_for_comparison,
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


def test_compare_copy_to_model_counts_missing_markers(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["### Résultat — mesure\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["### Interprétation\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["### Checklist finale\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** valeur correcte\n"]},
        ],
    )

    comparison = compare_copy_to_model(model, copy)

    assert comparison.model.response_cells == 1
    assert comparison.copy.response_cells == 1
    assert comparison.missing_response_cells == 0
    assert comparison.missing_result_cells == 1
    assert comparison.missing_interpretation_cells == 1
    assert comparison.missing_checklist_cells == 1


def test_compare_copy_to_model_formats_report(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["### Résultat — mesure\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [{"output_type": "stream", "text": ["ok\n"]}],
                "source": ["print('ok')\n"],
            },
        ],
    )

    comparison = compare_copy_to_model(model, copy)
    report = format_copy_comparison_report(comparison)

    assert "Comparaison modèle / copie" in report
    assert "Zones Réponse" in report
    assert "attendues dans le modèle : 1" in report
    assert "présentes dans la copie : 0" in report
    assert "Corrigeabilité comparative" in report
    assert "niveau : faible" in report
    assert "Retour possible à l'étudiant" in report


def test_compare_copy_student_feedback_mentions_execution_errors(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** valeur\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 2,
                "outputs": [{"output_type": "error", "ename": "ValueError"}],
                "source": ["raise ValueError()\n"],
            },
        ],
    )

    comparison = compare_copy_to_model(model, copy)

    assert comparison.readiness_level == "à reprendre"

    feedback = student_feedback_for_comparison(comparison)
    assert any("erreurs d'exécution" in message for message in feedback)
    assert any("Cellule 2" in message for message in feedback)

    report = format_copy_comparison_report(comparison)
    assert "Retour possible à l'étudiant" in report
    assert "Cellule 2 : erreur d'exécution à corriger" in report


def test_compare_copy_adds_readable_context_to_student_feedback(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Vérification de la loi de la réfraction\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** valeur\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 2,
                "outputs": [{"output_type": "error", "ename": "ValueError"}],
                "source": ["raise ValueError()\n"],
            },
        ],
    )

    comparison = compare_copy_to_model(model, copy)

    assert comparison.context_for_cell(3) == "partie « Vérification de la loi de la réfraction »"

    report = format_copy_comparison_report(comparison)
    assert "cellule 3 — partie « Vérification de la loi de la réfraction » — erreur d'exécution présente" in report
    assert "Cellule 3 — partie « Vérification de la loi de la réfraction » : erreur d'exécution à corriger" in report


def test_compare_copy_student_feedback_distinguishes_code_to_complete(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Tracé expérimental\n"]},
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

    comparison = compare_copy_to_model(model, copy)

    assert comparison.readiness_level == "à reprendre"

    feedback = student_feedback_for_comparison(comparison)
    assert any("code à compléter" in message for message in feedback)
    assert any("Cellule 2 — partie « Tracé expérimental » : complétez cette cellule puis exécutez-la." in message for message in feedback)
    assert any("Cellule 3 — partie « Tracé expérimental » : le code contient encore un « ? »" in message for message in feedback)
    assert any("Cellule 4 — partie « Tracé expérimental » : cellule de code à exécuter." in message for message in feedback)

    report = format_copy_comparison_report(comparison)
    assert "cellules à compléter : 2" in report
    assert "certaines cellules contiennent encore du code à compléter" in report

def test_export_copy_comparison_report_writes_text_file(tmp_path: Path) -> None:
    from tpstudio.copy_comparison import export_copy_comparison_report

    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"
    output = tmp_path / "rapport.txt"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["### Résultat — mesure\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** valeur\n"]},
        ],
    )

    exported = export_copy_comparison_report(model, copy, output)

    assert exported == output
    assert output.exists()

    text = output.read_text(encoding="utf-8")
    assert "Comparaison modèle / copie" in text
    assert "Retour possible à l'étudiant" in text


def test_export_copy_comparison_report_uses_default_name(tmp_path: Path) -> None:
    from tpstudio.copy_comparison import export_copy_comparison_report

    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie-etudiant.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** valeur\n"]},
        ],
    )

    exported = export_copy_comparison_report(model, copy)

    assert exported.name == "copie-etudiant-rapport-tpstudio.txt"
    assert exported.exists()
    assert "Comparaison modèle / copie" in exported.read_text(encoding="utf-8")
