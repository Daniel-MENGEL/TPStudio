from __future__ import annotations

import json
from pathlib import Path

from tpstudio.gradebook_bundle import GradebookBundlePaths
from tpstudio.gradebook_check import build_gradebook_check_summary
from tpstudio.gradebook_summary import write_gradebook_summary_html


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


def test_write_gradebook_summary_html_lists_missing_students(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n"
        "MARTIN,Bob,bob.martin@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "Durand-Alice.ipynb", [_identity_cell("Durand Alice")])

    check_summary = build_gradebook_check_summary(
        tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        kholle_week="25",
        students_file=students_file,
    )

    output = tmp_path / "bilan.html"

    result = write_gradebook_summary_html(
        output,
        copies_dir=tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        kholle_week="25",
        students_file=students_file,
        bundle_paths=GradebookBundlePaths(
            followup_csv=Path("suivi.csv"),
            unmatched_csv=Path("anomalies.csv"),
            missing_csv=Path("rapports-non-rendus.csv"),
        ),
        check_summary=check_summary,
    )

    assert result.path == output
    text = output.read_text(encoding="utf-8")

    assert "<!doctype html>" in text
    assert "Bilan TPStudio — Lois de Snell Descartes" in text
    assert "Rapports non rendus" in text
    assert "MARTIN Bob" in text
    assert "bob.martin@example.test" in text
    assert "suivi.csv" in text


def test_write_gradebook_summary_html_escapes_content(tmp_path: Path) -> None:
    output = tmp_path / "bilan.html"

    write_gradebook_summary_html(
        output,
        copies_dir=tmp_path,
        session="Séance <test>",
        tp_name="TP <danger>",
        kholle_week="25",
    )

    text = output.read_text(encoding="utf-8")

    assert "TP &lt;danger&gt;" in text
    assert "Séance &lt;test&gt;" in text
