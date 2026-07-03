from __future__ import annotations

import csv
import json
from pathlib import Path

from tpstudio.gradebook_bundle import (
    build_gradebook_bundle_paths,
    build_gradebook_bundle_prefix,
    export_gradebook_bundle,
    slugify_filename,
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


def test_slugify_filename() -> None:
    assert slugify_filename("Lois de Snell Descartes") == "Lois-de-Snell-Descartes"
    assert slugify_filename("Séance n°2 — optique") == "Seance-n2-optique"
    assert slugify_filename("  ") == "export-tpstudio"


def test_build_gradebook_bundle_prefix() -> None:
    assert build_gradebook_bundle_prefix(
        tp_name="Lois de Snell Descartes",
        kholle_week="25",
    ) == "Lois-de-Snell-Descartes-semaine-25"


def test_build_gradebook_bundle_paths(tmp_path: Path) -> None:
    paths = build_gradebook_bundle_paths(
        tmp_path,
        tp_name="Lois de Snell Descartes",
        kholle_week="25",
    )

    assert paths.followup_csv == tmp_path / "Lois-de-Snell-Descartes-semaine-25-suivi.csv"
    assert paths.unmatched_csv == tmp_path / "Lois-de-Snell-Descartes-semaine-25-anomalies.csv"
    assert paths.missing_csv == tmp_path / "Lois-de-Snell-Descartes-semaine-25-rapports-non-rendus.csv"


def test_export_gradebook_bundle_creates_three_csv_files(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    students_file.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n"
        "MARTIN,Bob,bob.martin@example.test,PCSI2-A\n",
        encoding="utf-8",
    )

    _write_notebook(tmp_path / "Durand-Alice.ipynb", [_identity_cell("Durand Alice")])

    paths = export_gradebook_bundle(
        tmp_path,
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        kholle_week="25",
        students_file=students_file,
    )

    assert paths.followup_csv.exists()
    assert paths.unmatched_csv.exists()
    assert paths.missing_csv.exists()

    with paths.followup_csv.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows[0]["Nom"] == "DURAND"
    assert rows[0]["Prénom"] == "Alice"

    with paths.missing_csv.open(encoding="utf-8", newline="") as stream:
        missing_rows = list(csv.DictReader(stream))

    assert missing_rows == [
        {
            "Nom": "MARTIN",
            "Prénom": "Bob",
            "Email": "bob.martin@example.test",
            "Raison": "rapport non rendu",
        }
    ]
