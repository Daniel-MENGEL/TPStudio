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


def test_cli_bundle_check_duplicates_creates_csv_and_updates_summaries(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "copie-1.ipynb", [_identity_cell("Durand Alice", week="25")])
    _write_notebook(tmp_path / "copie-2.ipynb", [_identity_cell("Alice Durand", week="26")])

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
            "--students-file",
            str(students_file),
            "--prefix",
            "export-test",
            "--summary-md",
            "--summary-html",
            "--check-duplicates",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    duplicates_csv = tmp_path / "export-test-doublons-suspects.csv"
    markdown = tmp_path / "export-test-bilan.md"
    html = tmp_path / "export-test-bilan.html"

    assert duplicates_csv.exists()
    assert markdown.exists()
    assert html.exists()

    assert "Doublons suspects" in result.stdout
    assert "Nombre de doublons suspects : 1" in result.stdout

    with duplicates_csv.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows[0]["Nom"] == "DURAND"
    assert rows[0]["Prénom"] == "Alice"
    assert rows[0]["Semaines de kholle n°"] == "25 ; 26"

    markdown_text = markdown.read_text(encoding="utf-8")
    html_text = html.read_text(encoding="utf-8")

    assert "## Doublons suspects" in markdown_text
    assert "Doublons suspects : 1" in markdown_text
    assert "DURAND Alice" in markdown_text

    assert "Doublons suspects" in html_text
    assert "Doublons suspects : 1" in html_text
    assert "DURAND" in html_text


def test_cli_bundle_duplicates_custom_output_path(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "copie-1.ipynb", [_identity_cell("Durand Alice", week="25")])
    _write_notebook(tmp_path / "copie-2.ipynb", [_identity_cell("Durand Alice", week="26")])

    output = tmp_path / "mon-fichier-doublons.csv"

    subprocess.run(
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
            "--duplicates-output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output.exists()
