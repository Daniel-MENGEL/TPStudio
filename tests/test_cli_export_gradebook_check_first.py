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


def _identity_cell(names: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## Identification du compte rendu\n",
            "\n",
            f"**Noms :** {names}\n",
            "**Groupe :** Binôme 3\n",
            "**Semaine de kholle n° :** 25\n",
        ],
    }


def test_cli_export_gradebook_check_first_does_not_block_missing_student(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n"
        "MARTIN,Bob,bob.martin@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "Durand-Alice.ipynb", [_identity_cell("Durand Alice")])

    output = tmp_path / "suivi.csv"
    missing_output = tmp_path / "copies-manquantes.csv"

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
            "--kholle-week",
            "25",
            "--students-file",
            str(students_file),
            "--check-first",
            "--missing-output",
            str(missing_output),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output.exists()
    assert missing_output.exists()
    assert "Contrôle TPStudio du suivi" in result.stdout
    assert "Copies manquantes : 1" in result.stdout
    assert "Fichier de suivi TPStudio créé" in result.stdout

    with missing_output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows == [
        {
            "Nom": "MARTIN",
            "Prénom": "Bob",
            "Email": "bob.martin@example.test",
            "Raison": "rapport non rendu",
        }
    ]


def test_cli_export_gradebook_check_first_exports_when_clean(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "Durand-Alice.ipynb", [_identity_cell("Durand Alice")])

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
            "--kholle-week",
            "25",
            "--students-file",
            str(students_file),
            "--check-first",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output.exists()
    assert "Contrôle TPStudio du suivi" in result.stdout
    assert "Aucune anomalie majeure détectée." in result.stdout
    assert "Fichier de suivi TPStudio créé" in result.stdout

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows[0]["Nom"] == "DURAND"


def test_cli_export_gradebook_check_first_blocks_unmatched_student(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "Inconnu-Test.ipynb", [_identity_cell("Inconnu Test")])

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
            "--kholle-week",
            "25",
            "--students-file",
            str(students_file),
            "--check-first",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert not output.exists()
    assert "Export interrompu" in result.stdout
    assert "Noms non reconnus : 1" in result.stdout


def test_cli_export_gradebook_allow_issues_forces_export(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "Inconnu-Test.ipynb", [_identity_cell("Inconnu Test")])

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
            "--kholle-week",
            "25",
            "--students-file",
            str(students_file),
            "--check-first",
            "--allow-issues",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output.exists()
    assert "Contrôle TPStudio du suivi" in result.stdout
    assert "Noms non reconnus : 1" in result.stdout
    assert "Fichier de suivi TPStudio créé" in result.stdout
