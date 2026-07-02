from __future__ import annotations

import json
from pathlib import Path

from tpstudio.copy_comparison import compare_copy_to_model
from tpstudio.copy_feedback import structured_feedback_markdown


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


def test_graph_issue_downgrades_global_readiness_in_feedback(tmp_path: Path) -> None:
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
                "outputs": [{"output_type": "stream", "text": ["ok\n"]}],
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
                "outputs": [{"output_type": "stream", "text": ["ok\n"]}],
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

    assert "Corrigeabilité globale : **à vérifier**" in markdown
    assert "au moins un graphe important est à vérifier" in markdown
    assert "Corrigeabilité technique" in markdown
    assert "Graphes à vérifier : **1**" in markdown


def test_clean_graph_keeps_global_readiness_from_technical_readiness(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    cells = [
        {"cell_type": "markdown", "metadata": {}, "source": ["## Vérification graphique\n"]},
        {
            "cell_type": "code",
            "metadata": {},
            "execution_count": 1,
            "outputs": [{"output_type": "stream", "text": ["ok\n"]}],
            "source": [
                "plt.plot(sini2, sini1, 'bo')\n",
                "plt.xlabel('$\\\\sin i_2$')\n",
                "plt.ylabel('$\\\\sin i_1$')\n",
                "a,b=np.polyfit(sini2,sini1,1)\n",
            ],
        },
    ]

    _write_notebook(model, cells)
    _write_notebook(copy, cells)

    comparison = compare_copy_to_model(model, copy)
    markdown = structured_feedback_markdown(comparison)

    assert "Corrigeabilité globale : **à vérifier**" not in markdown
    assert "Graphes à vérifier : **0**" in markdown
    assert "aucun blocage majeur détecté" in markdown
