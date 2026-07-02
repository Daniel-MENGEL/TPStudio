from __future__ import annotations

import csv
import json
from pathlib import Path

from tpstudio.copies_summary import (
    export_copies_summary_csv,
    summarize_copies,
    summarize_copy,
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


def test_summarize_copy_reports_response_and_graph_metrics(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "Alice-Durand.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Réponse\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["## Graphe\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [{"output_type": "stream", "text": ["ok\n"]}],
                "source": [
                    "plt.plot(sini2, sini1, 'bo')\n",
                    "plt.xlabel('$\\\\sin i_2$')\n",
                    "plt.ylabel('$\\\\sin i_1$')\n",
                ],
            },
        ],
    )
    _write_notebook(
        copy,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Réponse\n"]},
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**Réponse :** L'indice mesuré vaut 1,49, compatible avec l'indice attendu du plexiglas.\n"],
            },
            {"cell_type": "markdown", "metadata": {}, "source": ["## Graphe\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [{"output_type": "stream", "text": ["ok\n"]}],
                "source": [
                    "plt.plot(sini1, sini2, 'bo')\n",
                    "plt.xlabel('$\\\\sin i_1$')\n",
                    "plt.ylabel('$\\\\sin i_2$')\n",
                ],
            },
        ],
    )

    summary = summarize_copy(model, copy)

    assert summary.file == "Alice-Durand.ipynb"
    assert summary.responses_solid == 1
    assert summary.responses_fragile == 0
    assert summary.graphs_to_check == 1
    assert summary.global_readiness == "à vérifier"
    assert summary.main_reason == "au moins un graphe important est à vérifier"


def test_summarize_copies_ignores_model_and_feedback_notebooks(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "Bob-Martin.ipynb"
    feedback = tmp_path / "Bob-Martin-retour-tpstudio.ipynb"

    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": ["**Réponse :** L'indice 1,49 est compatible avec l'indice attendu du plexiglas.\n"],
        },
    ]

    _write_notebook(model, cells)
    _write_notebook(copy, cells)
    _write_notebook(feedback, cells)

    summaries = summarize_copies(model, tmp_path)

    assert [summary.file for summary in summaries] == ["Bob-Martin.ipynb"]


def test_export_copies_summary_csv(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "Claire-Roux.ipynb"
    output = tmp_path / "synthese.csv"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**Réponse :** Les valeurs sont proches donc c'est correct.\n"],
            },
        ],
    )

    created = export_copies_summary_csv(model, tmp_path, output)

    assert created == output
    assert output.exists()

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 1
    assert rows[0]["fichier"] == "Claire-Roux.ipynb"
    assert rows[0]["corrigeabilite_globale"]
    assert rows[0]["reponses_fragiles"] == "1"
