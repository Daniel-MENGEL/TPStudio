from __future__ import annotations

import json
from pathlib import Path

from tpstudio.graph_comparison import (
    compare_graphs,
    extract_graph_signatures,
    format_graph_comparison_report,
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


def test_extract_graph_signature_from_matplotlib_cell(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Vérification graphique\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [],
                "source": [
                    "sini1 = np.sin(i1)\n",
                    "sini2 = np.sin(i2)\n",
                    "plt.plot(sini2, sini1, 'bo', label='Points')\n",
                    "plt.xlabel('$\\sin i_2$')\n",
                    "plt.ylabel('$\\sin i_1$')\n",
                    "a,b=np.polyfit(sini2,sini1,1)\n",
                    "plt.legend(loc='best')\n",
                ],
            },
        ],
    )

    graphs = extract_graph_signatures(notebook)

    assert len(graphs) == 1
    graph = graphs[0]

    assert graph.cell_number == 2
    assert graph.context == "Vérification graphique"
    assert graph.function_name == "plt.plot"
    assert graph.x_expression == "sini2"
    assert graph.y_expression == "sini1"
    assert graph.xlabel == "$\\sin i_2$"
    assert graph.ylabel == "$\\sin i_1$"
    assert graph.has_legend is True
    assert graph.polyfit_x == "sini2"
    assert graph.polyfit_y == "sini1"


def test_compare_graphs_detects_inverted_axes(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        [
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [],
                "source": [
                    "plt.plot(sini2, sini1, 'bo')\n",
                    "plt.xlabel('$\\sin i_2$')\n",
                    "plt.ylabel('$\\sin i_1$')\n",
                    "a,b=np.polyfit(sini2,sini1,1)\n",
                ],
            },
        ],
    )
    _write_notebook(
        copy,
        [
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [],
                "source": [
                    "plt.plot(sini1, sini2, 'bo')\n",
                    "plt.xlabel('$\\sin i_1$')\n",
                    "plt.ylabel('$\\sin i_2$')\n",
                    "a,b=np.polyfit(sini1,sini2,1)\n",
                ],
            },
        ],
    )

    comparisons = compare_graphs(model, copy)

    assert len(comparisons) == 1
    comparison = comparisons[0]

    assert comparison.level == "à vérifier"
    assert any("axes probablement inversés" in finding for finding in comparison.findings)
    assert any("labels d'axes probablement inversés" in finding for finding in comparison.findings)
    assert any("régression linéaire probablement effectuée avec les axes inversés" in finding for finding in comparison.findings)


def test_compare_graphs_accepts_matching_graph(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    cells = [
        {
            "cell_type": "code",
            "metadata": {},
            "execution_count": 1,
            "outputs": [],
            "source": [
                "plt.plot(sini2, sini1, 'bo')\n",
                "plt.xlabel('$\\sin i_2$')\n",
                "plt.ylabel('$\\sin i_1$')\n",
                "a,b=np.polyfit(sini2,sini1,1)\n",
            ],
        },
    ]

    _write_notebook(model, cells)
    _write_notebook(copy, cells)

    comparison = compare_graphs(model, copy)[0]

    assert comparison.level == "cohérent"
    assert "expressions tracées cohérentes avec le modèle" in comparison.findings
    assert "régression linéaire cohérente avec le modèle" in comparison.findings


def test_format_graph_comparison_report(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        [
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
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [],
                "source": ["plt.plot(sini1, sini2)\n"],
            },
        ],
    )

    report = format_graph_comparison_report(model, copy)

    assert "TPStudio - Comparaison des graphes" in report
    assert "Graphes détectés dans le modèle : 1" in report
    assert "Graphes détectés dans la copie : 1" in report
    assert "axes probablement inversés" in report
