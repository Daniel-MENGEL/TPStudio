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


def test_cli_feedback_report_creates_markdown_report(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"
    output = tmp_path / "rapport.md"

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
            "feedback-report",
            str(model),
            str(copy),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output.exists()
    assert "Rapport TPStudio créé" in result.stdout
    assert "# Rapport TPStudio" in output.read_text(encoding="utf-8")
