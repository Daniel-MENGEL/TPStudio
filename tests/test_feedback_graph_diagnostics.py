from __future__ import annotations

import json
from pathlib import Path

from tpstudio.copy_comparison import compare_copy_to_model
from tpstudio.copy_feedback import (
    create_feedback_notebook,
    local_feedback_by_cell,
    structured_feedback_markdown,
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


def test_feedback_summary_includes_graph_diagnostics(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Vérification graphique\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [],
                "source": [
                    "plt.plot(sini2, sini1, 'bo')\n",
                    "plt.xlabel('$\\\\sin i_2$')\n",
                    "plt.ylabel('$\\\\sin i_1$')\n",
                    "a,b=np.polyfit(sini2,sini1,1)\n",
                ],
            },
        ],
    )
    _write_notebook(
        copy,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Vérification graphique\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [],
                "source": [
                    "plt.plot(sini1, sini2, 'bo')\n",
                    "plt.xlabel('$\\\\sin i_1$')\n",
                    "plt.ylabel('$\\\\sin i_2$')\n",
                    "a,b=np.polyfit(sini1,sini2,1)\n",
                ],
            },
        ],
    )

    comparison = compare_copy_to_model(model, copy)
    markdown = structured_feedback_markdown(comparison)

    assert "### Diagnostic des graphes" in markdown
    assert "Graphes analysés : **1**" in markdown
    assert "Graphes à vérifier : **1**" in markdown
    assert "axes probablement inversés" in markdown
    assert "labels d'axes probablement inversés" in markdown
    assert "régression linéaire probablement effectuée avec les axes inversés" in markdown


def test_feedback_copy_adds_local_comment_after_suspicious_graph(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"
    output = tmp_path / "copie-retour.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Vérification graphique\n"]},
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
            {"cell_type": "markdown", "metadata": {}, "source": ["## Vérification graphique\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [],
                "source": ["plt.plot(sini1, sini2)\n"],
            },
        ],
    )

    comparison = compare_copy_to_model(model, copy)
    comments = local_feedback_by_cell(comparison)

    assert 2 in comments
    assert any("Ce graphe est à vérifier" in comment for comment in comments[2])
    assert any("axes probablement inversés" in comment for comment in comments[2])

    created = create_feedback_notebook(model, copy, output)
    data = _read_notebook(created)
    cells = data["cells"]

    local_feedback_cells = [
        cell for cell in cells
        if cell.get("metadata", {}).get("tpstudio", {}).get("cell_role") == "local_feedback"
    ]

    assert local_feedback_cells
    assert any(
        "Ce graphe est à vérifier" in "".join(cell["source"])
        for cell in local_feedback_cells
    )
    assert data["metadata"]["tpstudio"]["graph_diagnostics_inserted"] is True
