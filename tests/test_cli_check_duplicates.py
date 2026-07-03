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


def test_cli_check_duplicates_reports_and_exports_csv(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "copie-1.ipynb", [_identity_cell("Durand Alice", week="25")])
    _write_notebook(tmp_path / "copie-2.ipynb", [_identity_cell("Alice Durand", week="26")])

    output = tmp_path / "doublons-suspects.csv"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tpstudio.cli",
            "check-duplicates",
            str(tmp_path),
            "--session",
            "Séance n°2",
            "--tp-name",
            "Lois de Snell Descartes",
            "--kholle-week",
            "25",
            "--students-file",
            str(students_file),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Doublons suspects TPStudio" in result.stdout
    assert "Doublons suspects : 1" in result.stdout
    assert "DURAND Alice" in result.stdout
    assert "Semaines de kholle n° : 25 ; 26" in result.stdout
    assert "Fichier de doublons suspects créé" in result.stdout

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows[0]["Nom"] == "DURAND"
    assert rows[0]["Prénom"] == "Alice"
    assert rows[0]["Semaines de kholle n°"] == "25 ; 26"


def test_cli_check_duplicates_without_duplicates(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "copie-1.ipynb", [_identity_cell("Durand Alice")])

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tpstudio.cli",
            "check-duplicates",
            str(tmp_path),
            "--session",
            "Séance n°2",
            "--tp-name",
            "Lois de Snell Descartes",
            "--kholle-week",
            "25",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Doublons suspects : 0" in result.stdout
    assert "Aucun doublon suspect détecté." in result.stdout
