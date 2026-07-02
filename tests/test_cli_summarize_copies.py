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


def test_cli_summarize_copies_creates_csv(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "Alice-Durand.ipynb"
    output = tmp_path / "synthese.csv"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**Réponse :** L'indice 1,49 est compatible avec l'indice attendu du plexiglas.\n"],
            },
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tpstudio.cli",
            "summarize-copies",
            str(model),
            str(tmp_path),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output.exists()
    assert "Synthèse TPStudio créée" in result.stdout

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 1
    assert rows[0]["fichier"] == "Alice-Durand.ipynb"
