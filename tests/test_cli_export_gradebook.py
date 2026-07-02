from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


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


def test_cli_export_gradebook_creates_csv(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

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
                    "**Semaine :** 25\n",
                ],
            }
        ],
    )
    output = tmp_path / "suivi.csv"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tpstudio.cli",
            "export-gradebook",
            str(tmp_path),
            "--session",
            "Séance n°2",
            "--tp-name",
            "Lois de Snell Descartes",
            "--week",
            "24",
            "--students-file",
            str(students_file),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output.exists()
    assert "Fichier de suivi TPStudio créé" in result.stdout

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows[0]["Nom"] == "DURAND"
    assert rows[0]["Prénom"] == "Alice"
    assert rows[0]["Email"] == "alice.durand@example.test"
    assert rows[0]["Groupe"] == "PCSI2"
    assert rows[0]["Semaine de kholle n°"] == "25"


def test_cli_export_gradebook_creates_unmatched_report(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(
        tmp_path / "Inconnu-Test.ipynb",
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Identification du compte rendu\n",
                    "\n",
                    "**Noms :** Inconnu Test\n",
                    "**Groupe :** Binôme 4\n",
                    "**Semaine :** 25\n",
                ],
            }
        ],
    )

    output = tmp_path / "suivi.csv"
    unmatched = tmp_path / "anomalies.csv"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tpstudio.cli",
            "export-gradebook",
            str(tmp_path),
            "--session",
            "Séance n°2",
            "--tp-name",
            "Lois de Snell Descartes",
            "--students-file",
            str(students_file),
            "--unmatched-output",
            str(unmatched),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output.exists()
    assert unmatched.exists()
    assert "Fichier de suivi TPStudio créé" in result.stdout

    with unmatched.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows[0]["Nom saisi"] == "INCONNU"
    assert rows[0]["Prénom saisi"] == "Test"
    assert rows[0]["Semaine de kholle n°"] == "25"
    assert rows[0]["Raison"] == "étudiant non trouvé dans la liste officielle"


def test_cli_export_gradebook_keeps_legacy_date_option_as_week_fallback(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "Durand-Alice.ipynb", [])

    output = tmp_path / "suivi.csv"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "tpstudio.cli",
            "export-gradebook",
            str(tmp_path),
            "--session",
            "Séance n°2",
            "--tp-name",
            "Lois de Snell Descartes",
            "--date",
            "25",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows[0]["Semaine de kholle n°"] == "25"


def test_cli_export_gradebook_creates_missing_report(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n"
        "MARTIN,Bob,bob.martin@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

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
                    "**Groupe :** Binôme 4\n",
                    "**Semaine de kholle n° :** 25\n",
                ],
            }
        ],
    )

    output = tmp_path / "suivi.csv"
    missing = tmp_path / "copies-manquantes.csv"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tpstudio.cli",
            "export-gradebook",
            str(tmp_path),
            "--session",
            "Séance n°2",
            "--tp-name",
            "Lois de Snell Descartes",
            "--students-file",
            str(students_file),
            "--missing-output",
            str(missing),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output.exists()
    assert missing.exists()
    assert "Fichier de suivi TPStudio créé" in result.stdout

    with missing.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows == [
        {
            "Nom": "MARTIN",
            "Prénom": "Bob",
            "Email": "bob.martin@example.test",
            "Raison": "aucune copie détectée pour cet étudiant",
        }
    ]
