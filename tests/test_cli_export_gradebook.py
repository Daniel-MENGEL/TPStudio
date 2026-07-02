
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def _write_notebook(path: Path, cells: list[dict]) -> None:
    path.write_text(json.dumps({"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}, ensure_ascii=False), encoding="utf-8")


def test_cli_export_gradebook_creates_csv(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text("Nom,Prénom,Email,Groupe\nDURAND,Alice,alice.durand@example.test,PCSI2-A\n", encoding="utf-8")
    _write_notebook(tmp_path / "Durand-Alice.ipynb", [{"cell_type": "markdown", "metadata": {}, "source": ["## Identification du compte rendu\n", "\n", "**Noms :** Durand Alice\n", "**Groupe :** PCSI2\n", "**Date de la séance :** 2026-07-02\n"]}])
    output = tmp_path / "suivi.csv"
    result = subprocess.run([
        sys.executable, "-m", "tpstudio.cli", "export-gradebook", str(tmp_path),
        "--session", "Séance n°2", "--tp-name", "Lois de Snell Descartes", "--date", "2026-07-01",
        "--students-file", str(students_file), "--output", str(output)
    ], check=True, capture_output=True, text=True)
    assert output.exists()
    assert "Fichier de suivi TPStudio créé" in result.stdout
    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["Nom"] == "DURAND"
    assert rows[0]["Prénom"] == "Alice"
    assert rows[0]["Email"] == "alice.durand@example.test"
    assert rows[0]["Groupe"] == "PCSI2"
    assert rows[0]["Date"] == "2026-07-02"
