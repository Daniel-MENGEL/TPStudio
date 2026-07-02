from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


def _write_notebook(path: Path) -> None:
    path.write_text(
        '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}',
        encoding="utf-8",
    )


def test_cli_export_gradebook_creates_csv(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "Durand-Alice.ipynb")
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
            "--date",
            "2026-07-02",
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
