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


def test_cli_correct_copy_creates_correction_bundle(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "Alice-Durand.ipynb"
    output_dir = tmp_path / "corrections"

    _write_notebook(
        model,
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**Réponse :**\n\n"],
            }
        ],
    )
    _write_notebook(
        copy,
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "**Réponse :** L'indice 1,49 est compatible avec la valeur attendue.\n"
                ],
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tpstudio.cli",
            "correct-copy",
            str(model),
            str(copy),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    notebook = output_dir / "Alice-Durand-correction.ipynb"
    report = output_dir / "Alice-Durand-correction.md"

    assert notebook.exists()
    assert report.exists()

    assert "Correction TPStudio créée" in result.stdout
    assert str(notebook) in result.stdout
    assert str(report) in result.stdout


def test_cli_correct_copy_refuses_existing_outputs_without_overwrite(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "Alice-Durand.ipynb"
    output_dir = tmp_path / "corrections"

    _write_notebook(
        model,
        [{"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]}],
    )
    _write_notebook(
        copy,
        [{"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** test\n"]}],
    )

    output_dir.mkdir()
    (output_dir / "Alice-Durand-correction.ipynb").write_text(
        "à conserver",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tpstudio.cli",
            "correct-copy",
            str(model),
            str(copy),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "--overwrite" in (result.stdout + result.stderr)
