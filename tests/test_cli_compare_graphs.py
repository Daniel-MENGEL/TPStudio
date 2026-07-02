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


def test_cli_compare_graphs(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        [
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [],
                "source": ["plt.plot(sini2, sini1)\n"],
            },
        ],
    )
    _write_notebook(
        copy,
        [
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [],
                "source": ["plt.plot(sini1, sini2)\n"],
            },
        ],
    )

    result = subprocess.run(
        [sys.executable, "-m", "tpstudio.cli", "compare-graphs", str(model), str(copy)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "TPStudio - Comparaison des graphes" in result.stdout
    assert "axes probablement inversés" in result.stdout
