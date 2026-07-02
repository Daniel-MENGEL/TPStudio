from __future__ import annotations

import json
from pathlib import Path

from tpstudio.gradebook_check import (
    build_gradebook_check_summary,
    format_gradebook_check_summary,
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


def _identity_cell(names: str, group: str = "Binôme 3", week: str = "25") -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## Identification du compte rendu\n",
            "\n",
            f"**Noms :** {names}\n",
            f"**Groupe :** {group}\n",
            f"**Semaine de kholle n° :** {week}\n",
        ],
    }


def test_build_gradebook_check_summary_counts_main_cases(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n"
        "MARTIN,Bob,bob.martin@example.test,PCSI2-A\n"
        "DUPONT,Claire,claire.dupont@example.test,PCSI2-B\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "copie-durand.ipynb", [_identity_cell("Durand Alice")])
    _write_notebook(tmp_path / "copie-inconnue.ipynb", [_identity_cell("Inconnu Test")])
    _write_notebook(tmp_path / "Lois-de-Snell-Descartes.ipynb", [])

    summary = build_gradebook_check_summary(
        tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        kholle_week="25",
        students_file=students_file,
    )

    assert summary.notebooks_found == 3
    assert summary.notebooks_analyzed == 2
    assert summary.notebooks_ignored == 1
    assert summary.gradebook_rows == 2
    assert summary.detected_students == 2
    assert summary.unmatched_named_students == 1
    assert summary.missing_identity_notebooks == 0
    assert summary.missing_students == 2


def test_format_gradebook_check_summary() -> None:
    summary = build_gradebook_check_summary(
        Path("/does/not/exist"),
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        kholle_week="25",
    )

    text = format_gradebook_check_summary(summary)

    assert "Contrôle TPStudio du suivi" in text
    assert "TP : Lois de Snell Descartes" in text
    assert "Séance : Séance n°2" in text
    assert "Semaine de kholle n° : 25" in text
    assert "Notebooks trouvés : 0" in text
    assert "Aucune anomalie majeure détectée." in text


def test_format_gradebook_check_summary_shows_pattern() -> None:
    summary = build_gradebook_check_summary(
        Path("/does/not/exist"),
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        kholle_week="25",
        pattern="*Snell*.ipynb",
    )

    text = format_gradebook_check_summary(summary)

    assert "Motif de fichiers : *Snell*.ipynb" in text
