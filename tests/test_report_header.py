from __future__ import annotations

import json
from pathlib import Path

from tpstudio.report_header import (
    CONSIGNES_RAPPORT_URL,
    ensure_report_identity_cell,
    has_report_identity_cell,
    postprocess_improved_notebook,
    postprocess_improved_notebooks_in_target,
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


def _read_notebook(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_postprocess_inserts_identity_after_pdf_link_and_removes_duplicates(tmp_path: Path) -> None:
    notebook = tmp_path / "TP-ameliore.ipynb"

    improvement = {
        "cell_type": "markdown",
        "metadata": {},
        "source": ["---\n\n## 🛠 Améliorations proposées par TPStudio\n\nPremier bloc\n"],
    }
    evaluation = {
        "cell_type": "markdown",
        "metadata": {},
        "source": ["---\n\n## 📊 Évaluation par compétences\n\nPremier bloc\n"],
    }

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["# Titre du TP\n\n[Pdf complet](https://example.test/tp.pdf)\n"]},
            {"cell_type": "code", "metadata": {}, "source": ["x = 1\n"], "execution_count": None, "outputs": []},
            improvement,
            evaluation,
            dict(improvement),
            dict(evaluation),
        ],
    )

    result = postprocess_improved_notebook(notebook)

    assert result.changed is True
    assert result.identity_inserted is True
    assert result.duplicate_generated_cells_removed == 2

    data = _read_notebook(notebook)
    cells = data["cells"]

    assert "Pdf complet" in "".join(cells[0]["source"])

    identity_source = "".join(cells[1]["source"])
    assert "Noms :" in identity_source
    assert "Groupe :" in identity_source
    assert "Semaine de kholle n° :" in identity_source
    assert "Date de la séance" not in identity_source
    assert CONSIGNES_RAPPORT_URL in identity_source

    all_sources = ["".join(cell.get("source", [])) for cell in cells]
    assert sum("Améliorations proposées par TPStudio" in source for source in all_sources) == 1
    assert sum("Évaluation par compétences" in source for source in all_sources) == 1
    assert data["metadata"]["tpstudio"]["improve_postprocessed"] is True


def test_postprocess_is_idempotent(tmp_path: Path) -> None:
    notebook = tmp_path / "TP-ameliore.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["# Titre\n\n[Pdf complet](https://example.test/tp.pdf)\n"]},
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["---\n\n## 🛠 Améliorations proposées par TPStudio\n"],
            },
        ],
    )

    first = postprocess_improved_notebook(notebook)
    second = postprocess_improved_notebook(notebook)
    data = _read_notebook(notebook)

    assert first.changed is True
    assert second.changed is False
    assert sum(1 for cell in data["cells"] if has_report_identity_cell([cell])) == 1


def test_postprocess_target_processes_generated_notebook_even_without_ameliore_name(tmp_path: Path) -> None:
    notebook = tmp_path / "Copie-etudiant.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["# TP\n\n[Pdf complet](https://example.test/tp.pdf)\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["## Évaluation par compétences\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["## Évaluation par compétences\n"]},
        ],
    )

    results = postprocess_improved_notebooks_in_target(tmp_path)

    assert len(results) == 1
    assert results[0].changed is True

    data = _read_notebook(notebook)
    sources = ["".join(cell.get("source", [])) for cell in data["cells"]]

    assert any("Noms :" in source for source in sources)
    assert any("Semaine de kholle n° :" in source for source in sources)
    assert sum("Évaluation par compétences" in source for source in sources) == 1


def test_ensure_report_identity_cell_keeps_backward_compatibility(tmp_path: Path) -> None:
    notebook = tmp_path / "TP-ameliore.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["# Titre\n\n[Pdf complet](https://example.test/tp.pdf)\n"]},
        ],
    )

    assert ensure_report_identity_cell(notebook) is True
    assert ensure_report_identity_cell(notebook) is False


def test_has_report_identity_cell_detects_markdown_labels_without_metadata() -> None:
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Identification du compte rendu\n",
                "\n",
                "**Noms :**  \n",
                "**Groupe :**  \n",
                "**Semaine :**  \n",
            ],
        }
    ]

    assert has_report_identity_cell(cells) is True


def test_has_report_identity_cell_still_detects_legacy_date_label() -> None:
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Identification du compte rendu\n",
                "\n",
                "**Noms :**  \n",
                "**Groupe :**  \n",
                "**Date de la séance :**  \n",
            ],
        }
    ]

    assert has_report_identity_cell(cells) is True
