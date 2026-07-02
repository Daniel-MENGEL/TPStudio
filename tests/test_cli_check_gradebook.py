from __future__ import annotations

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


def test_cli_check_gradebook_prints_summary(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n"
        "MARTIN,Bob,bob.martin@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(
        tmp_path / "copie-durand.ipynb",
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Identification du compte rendu\n",
                    "\n",
                    "**Noms :** Durand Alice\n",
                    "**Groupe :** Binôme 3\n",
                    "**Semaine de kholle n° :** 25\n",
                ],
            }
        ],
    )
    _write_notebook(tmp_path / "Lois-de-Snell-Descartes.ipynb", [])

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tpstudio.cli",
            "check-gradebook",
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

    assert "Contrôle TPStudio du suivi" in result.stdout
    assert "Notebooks trouvés : 2" in result.stdout
    assert "Notebooks analysés : 1" in result.stdout
    assert "Notebooks ignorés : 1" in result.stdout
    assert "Étudiants détectés : 1" in result.stdout
    assert "Copies manquantes : 1" in result.stdout
