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


def test_cli_export_gradebook_bundle_creates_three_csv_files(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n"
        "MARTIN,Bob,bob.martin@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "Durand-Alice.ipynb", [_identity_cell("Durand Alice")])

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tpstudio.cli",
            "export-gradebook-bundle",
            str(tmp_path),
            "--session",
            "Séance n°2",
            "--tp-name",
            "Lois de Snell Descartes",
            "--kholle-week",
            "25",
            "--students-file",
            str(students_file),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    followup = tmp_path / "Lois-de-Snell-Descartes-semaine-25-suivi.csv"
    anomalies = tmp_path / "Lois-de-Snell-Descartes-semaine-25-anomalies.csv"
    missing = tmp_path / "Lois-de-Snell-Descartes-semaine-25-rapports-non-rendus.csv"

    assert followup.exists()
    assert anomalies.exists()
    assert missing.exists()
    assert "Bundle de suivi TPStudio créé" in result.stdout
    assert str(followup) in result.stdout
    assert str(anomalies) in result.stdout
    assert str(missing) in result.stdout

    with missing.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows[0]["Nom"] == "MARTIN"
