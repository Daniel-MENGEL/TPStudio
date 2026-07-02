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


def test_feedback_keeps_pedagogical_findings_when_global_readiness_is_to_rework(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Code à compléter\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [{"output_type": "stream", "text": ["ok\n"]}],
                "source": ["x = 1\n"],
            },
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
            {"cell_type": "markdown", "metadata": {}, "source": ["## Code à compléter\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["x = ?\n"],
            },
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

    assert "Corrigeabilité globale : **à reprendre**" in markdown
    assert "Raison principale : **blocages techniques prioritaires**" in markdown
    assert "Points pédagogiques déjà détectés : 1 graphe à vérifier." in markdown
    assert "Graphes à vérifier : **1**" in markdown
