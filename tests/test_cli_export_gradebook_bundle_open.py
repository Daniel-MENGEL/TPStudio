from __future__ import annotations

import json
import os
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


def test_cli_export_gradebook_bundle_open_summary_prefers_html(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "Durand-Alice.ipynb", [_identity_cell("Durand Alice")])

    env = os.environ.copy()
    env["TPSTUDIO_OPEN_DRY_RUN"] = "1"

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
            "--prefix",
            "export-test",
            "--summary-md",
            "--summary-html",
            "--open-summary",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "Ouverture du bilan" in result.stdout
    assert "export-test-bilan.html" in result.stdout


def test_cli_export_gradebook_bundle_open_folder(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "Durand-Alice.ipynb", [_identity_cell("Durand Alice")])

    env = os.environ.copy()
    env["TPSTUDIO_OPEN_DRY_RUN"] = "1"

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
            "--prefix",
            "export-test",
            "--open-folder",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "Ouverture du dossier" in result.stdout
    assert str(tmp_path) in result.stdout


def test_cli_export_gradebook_bundle_open_summary_without_summary_warns(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "Durand-Alice.ipynb", [_identity_cell("Durand Alice")])

    env = os.environ.copy()
    env["TPSTUDIO_OPEN_DRY_RUN"] = "1"

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
            "--prefix",
            "export-test",
            "--open-summary",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "Aucun bilan à ouvrir" in result.stdout
    assert "--summary-html" in result.stdout
