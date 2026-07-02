from __future__ import annotations

import csv
import json
from pathlib import Path

from tpstudio.gradebook_export import (
    NotebookIdentity,
    build_gradebook_rows,
    export_gradebook_csv,
    extract_identity_from_text,
    infer_student_name_from_notebook,
    read_notebook_identity,
    split_identity_names,
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


def test_extract_identity_from_markdown_text() -> None:
    identity = extract_identity_from_text(
        "## Identification du compte rendu\n"
        "\n"
        "**Noms :** Durand Alice\n"
        "**Groupe :** PCSI2\n"
        "**Date de la séance :** 2026-07-02\n"
    )

    assert identity == NotebookIdentity(
        names="Durand Alice",
        group="PCSI2",
        session_date="2026-07-02",
    )


def test_read_notebook_identity_from_tpsudio_metadata(tmp_path: Path) -> None:
    notebook = tmp_path / "Durand-Alice.ipynb"

    _write_notebook(
        notebook,
        [
            {
                "cell_type": "markdown",
                "metadata": {
                    "tpstudio": {
                        "cell_role": "report_identity",
                    }
                },
                "source": [
                    "## Identification du compte rendu\n",
                    "\n",
                    "**Noms :** Durand Alice\n",
                    "**Groupe :** PCSI2\n",
                    "**Date de la séance :** 2026-07-02\n",
                ],
            }
        ],
    )

    assert read_notebook_identity(notebook) == NotebookIdentity(
        names="Durand Alice",
        group="PCSI2",
        session_date="2026-07-02",
    )


def test_split_identity_names_is_prudent() -> None:
    assert split_identity_names("Durand Alice") == ("DURAND", "Alice")
    assert split_identity_names("Durand Alice et Martin Bob") == (
        "Durand Alice et Martin Bob",
        "",
    )
    assert split_identity_names("") == ("", "")


def test_infer_student_name_from_notebook() -> None:
    assert infer_student_name_from_notebook("Durand-Alice.ipynb") == ("DURAND", "Alice")
    assert infer_student_name_from_notebook("DURAND_Alice.ipynb") == ("DURAND", "Alice")
    assert infer_student_name_from_notebook("Martin Bob.ipynb") == ("MARTIN", "Bob")
    assert infer_student_name_from_notebook("copie-Dupont-Marie.ipynb") == ("DUPONT", "Marie")


def test_infer_student_name_leaves_tp_title_empty_when_no_student_name() -> None:
    assert infer_student_name_from_notebook(
        "Lois-de-Snell-Descartes.ipynb",
        tp_name="Lois de Snell Descartes",
    ) == ("", "")

    assert infer_student_name_from_notebook(
        "Lois-de-Snell-Descartes-codex.ipynb",
        tp_name="Lois de Snell Descartes",
    ) == ("", "")


def test_build_gradebook_rows_uses_notebook_identity_first(tmp_path: Path) -> None:
    _write_notebook(
        tmp_path / "Lois-de-Snell-Descartes-codex.ipynb",
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Identification du compte rendu\n",
                    "\n",
                    "**Noms :** Durand Alice\n",
                    "**Groupe :** PCSI2\n",
                    "**Date de la séance :** 2026-07-02\n",
                ],
            }
        ],
    )

    rows = build_gradebook_rows(
        tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        date_value="2026-07-01",
    )

    assert len(rows) == 1
    assert rows[0].last_name == "DURAND"
    assert rows[0].first_name == "Alice"
    assert rows[0].group == "PCSI2"
    assert rows[0].date == "2026-07-02"


def test_build_gradebook_rows_keeps_unknown_name_empty(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "Lois-de-Snell-Descartes.ipynb", [])
    _write_notebook(tmp_path / "Lois-de-Snell-Descartes-codex.ipynb", [])

    rows = build_gradebook_rows(
        tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        date_value="2026-07-02",
    )

    assert [row.notebook_name for row in rows] == [
        "Lois-de-Snell-Descartes-codex.ipynb",
        "Lois-de-Snell-Descartes.ipynb",
    ]
    assert rows[0].last_name == ""
    assert rows[0].first_name == ""
    assert rows[1].last_name == ""
    assert rows[1].first_name == ""


def test_build_gradebook_rows_ignores_generated_feedback_notebooks(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "Durand-Alice.ipynb", [])
    _write_notebook(tmp_path / "Martin-Bob.ipynb", [])
    _write_notebook(tmp_path / "Martin-Bob-retour-tpstudio.ipynb", [])

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


def test_export_gradebook_csv(tmp_path: Path) -> None:
    _write_notebook(
        tmp_path / "Durand-Alice.ipynb",
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Identification du compte rendu\n",
                    "\n",
                    "**Noms :** Durand Alice\n",
                    "**Groupe :** PCSI2\n",
                    "**Date de la séance :** 2026-07-02\n",
                ],
            }
        ],
    )
    output = tmp_path / "suivi.csv"

    created = export_gradebook_csv(
        tmp_path,
        output,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        date_value="2026-07-01",
    )

    assert created == output
    assert output.exists()

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 1
    assert rows[0]["Nom"] == "DURAND"
    assert rows[0]["Prénom"] == "Alice"
    assert rows[0]["Groupe"] == "PCSI2"
    assert rows[0]["Séance"] == "Séance n°2"
    assert rows[0]["Nom du TP"] == "Lois de Snell Descartes"
    assert rows[0]["Nom du notebook"] == "Durand-Alice.ipynb"
    assert rows[0]["Date"] == "2026-07-02"
    assert rows[0]["Note"] == ""
