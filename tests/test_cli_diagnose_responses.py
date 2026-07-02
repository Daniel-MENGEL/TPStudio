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


def test_cli_diagnose_responses(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Analyse\n"]},
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**Réponse :** Les valeurs sont proches donc c'est correct.\n"],
            },
        ],
    )

    result = subprocess.run(
        [sys.executable, "-m", "tpstudio.cli", "diagnose-responses", str(notebook)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Diagnostic des réponses étudiantes" in result.stdout
    assert "Réponses analysées : 1" in result.stdout
    assert "partie « Analyse »" in result.stdout
    assert "niveau : fragile" in result.stdout
