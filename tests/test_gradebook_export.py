from __future__ import annotations

import csv
from pathlib import Path

from tpstudio.gradebook_export import (
    build_gradebook_rows,
    export_gradebook_csv,
    infer_student_name_from_notebook,
)


def _write_notebook(path: Path) -> None:
    path.write_text(
        '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}',
        encoding="utf-8",
    )


def test_infer_student_name_from_notebook() -> None:
    assert infer_student_name_from_notebook("Durand-Alice.ipynb") == ("DURAND", "Alice")
    assert infer_student_name_from_notebook("DURAND_Alice.ipynb") == ("DURAND", "Alice")
    assert infer_student_name_from_notebook("Martin Bob.ipynb") == ("MARTIN", "Bob")
    assert infer_student_name_from_notebook("copie-Dupont-Marie.ipynb") == ("DUPONT", "Marie")


def test_build_gradebook_rows_ignores_generated_notebooks(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "Durand-Alice.ipynb")
    _write_notebook(tmp_path / "Martin-Bob.ipynb")
    _write_notebook(tmp_path / "Martin-Bob-retour-tpstudio.ipynb")
    _write_notebook(tmp_path / "Lois-de-Snell-Descartes-ameliore.ipynb")

    rows = build_gradebook_rows(
        tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        date_value="2026-07-02",
    )

    assert [row.notebook_name for row in rows] == [
        "Durand-Alice.ipynb",
        "Martin-Bob.ipynb",
    ]

    assert rows[0].last_name == "DURAND"
    assert rows[0].first_name == "Alice"
    assert rows[0].session == "Séance n°2"
    assert rows[0].tp_name == "Lois de Snell Descartes"
    assert rows[0].date == "2026-07-02"
    assert rows[0].grade == ""


def test_export_gradebook_csv(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "Durand-Alice.ipynb")
    output = tmp_path / "suivi.csv"

    created = export_gradebook_csv(
        tmp_path,
        output,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        date_value="2026-07-02",
    )

    assert created == output
    assert output.exists()

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 1
    assert rows[0]["Nom"] == "DURAND"
    assert rows[0]["Prénom"] == "Alice"
    assert rows[0]["Séance"] == "Séance n°2"
    assert rows[0]["Nom du TP"] == "Lois de Snell Descartes"
    assert rows[0]["Nom du notebook"] == "Durand-Alice.ipynb"
    assert rows[0]["Date"] == "2026-07-02"
    assert rows[0]["Note"] == ""
