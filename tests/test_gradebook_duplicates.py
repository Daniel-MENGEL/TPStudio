from __future__ import annotations

import csv
import json
from pathlib import Path

from tpstudio.gradebook_duplicates import (
    build_duplicate_submissions,
    export_duplicate_submissions_csv,
    format_duplicate_submissions_report,
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


def _identity_cell(names: str, week: str = "25") -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## Identification du compte rendu\n",
            "\n",
            f"**Noms :** {names}\n",
            "**Groupe :** Binôme 3\n",
            f"**Semaine de kholle n° :** {week}\n",
        ],
    }


def test_build_duplicate_submissions_detects_same_student_same_tp_same_week(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "copie-1.ipynb", [_identity_cell("Durand Alice", week="25")])
    _write_notebook(tmp_path / "copie-2.ipynb", [_identity_cell("Alice Durand", week="25")])

    duplicates = build_duplicate_submissions(
        tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        week_value="25",
        students_file=students_file,
    )

    assert len(duplicates) == 1
    assert duplicates[0].last_name == "DURAND"
    assert duplicates[0].first_name == "Alice"
    assert duplicates[0].email == "alice.durand@example.test"
    assert duplicates[0].weeks == ("25",)
    assert duplicates[0].notebook_names == ("copie-1.ipynb", "copie-2.ipynb")


def test_build_duplicate_submissions_detects_same_student_same_tp_even_different_weeks(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "copie-semaine-25.ipynb", [_identity_cell("Durand Alice", week="25")])
    _write_notebook(tmp_path / "copie-semaine-26.ipynb", [_identity_cell("Alice Durand", week="26")])

    duplicates = build_duplicate_submissions(
        tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        students_file=students_file,
    )

    assert len(duplicates) == 1
    assert duplicates[0].weeks == ("25", "26")
    assert duplicates[0].notebook_names == (
        "copie-semaine-25.ipynb",
        "copie-semaine-26.ipynb",
    )


def test_build_duplicate_submissions_ignores_single_notebook(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "copie-1.ipynb", [_identity_cell("Durand Alice")])

    duplicates = build_duplicate_submissions(
        tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        week_value="25",
    )

    assert duplicates == []


def test_export_duplicate_submissions_csv(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "copie-1.ipynb", [_identity_cell("Durand Alice", week="25")])
    _write_notebook(tmp_path / "copie-2.ipynb", [_identity_cell("Durand Alice", week="26")])

    duplicates = build_duplicate_submissions(
        tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
    )

    output = export_duplicate_submissions_csv(
        duplicates,
        tmp_path / "doublons-suspects.csv",
    )

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 1
    assert rows[0]["Nom"] == "DURAND"
    assert rows[0]["Prénom"] == "Alice"
    assert rows[0]["Nom du TP"] == "Lois de Snell Descartes"
    assert rows[0]["Semaines de kholle n°"] == "25 ; 26"
    assert "copie-1.ipynb" in rows[0]["Notebooks"]
    assert "copie-2.ipynb" in rows[0]["Notebooks"]


def test_format_duplicate_submissions_report_without_duplicates() -> None:
    text = format_duplicate_submissions_report(
        [],
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        week_value="25",
    )

    assert "Doublons suspects : 0" in text
    assert "Aucun doublon suspect détecté." in text
