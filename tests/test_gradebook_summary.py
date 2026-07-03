from __future__ import annotations

import json
from pathlib import Path

from tpstudio.gradebook_bundle import GradebookBundlePaths
from tpstudio.gradebook_check import build_gradebook_check_summary
from tpstudio.gradebook_summary import (
    format_gradebook_summary_markdown,
    write_gradebook_summary_markdown,
)


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


def test_format_gradebook_summary_markdown_clean() -> None:
    text = format_gradebook_summary_markdown(
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        kholle_week="25",
        bundle_paths=GradebookBundlePaths(
            followup_csv=Path("suivi.csv"),
            unmatched_csv=Path("anomalies.csv"),
            missing_csv=Path("rapports-non-rendus.csv"),
        ),
    )

    assert "# Bilan TPStudio — Lois de Snell Descartes" in text
    assert "**Séance :** Séance n°2" in text
    assert "**Semaine de kholle n° :** 25" in text
    assert "- Suivi : `suivi.csv`" in text
    assert "Aucune anomalie à vérifier." in text
    assert "Aucun rapport non rendu signalé." in text


def test_write_gradebook_summary_markdown_lists_missing_students(tmp_path: Path) -> None:
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

    output = tmp_path / "bilan.md"

    result = write_gradebook_summary_markdown(
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
    assert "## Résumé" in text
    assert "- Rapports non rendus : 1" in text
    assert "- MARTIN Bob — bob.martin@example.test" in text


def test_write_gradebook_summary_markdown_lists_unmatched_students(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "Inconnu-Test.ipynb", [_identity_cell("Inconnu Test")])

    check_summary = build_gradebook_check_summary(
        tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        kholle_week="25",
        students_file=students_file,
    )

    output = tmp_path / "bilan.md"

    write_gradebook_summary_markdown(
        output,
        copies_dir=tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        kholle_week="25",
        students_file=students_file,
        check_summary=check_summary,
    )

    text = output.read_text(encoding="utf-8")
    assert "## Anomalies à vérifier" in text
    assert "INCONNU Test" in text
    assert "étudiant non trouvé dans la liste officielle" in text
