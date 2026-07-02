from __future__ import annotations

import json
from pathlib import Path

from tpstudio.response_extraction import (
    extract_responses_from_notebook,
    format_response_extraction_report,
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


def test_extract_responses_from_markdown_cells(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Loi de la réfraction\n"]},
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**Réponse :** La pente vaut environ 1,5, ce qui correspond à l'indice du plexiglas.\n"],
            },
            {"cell_type": "markdown", "metadata": {}, "source": ["### Interprétation\n"]},
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["Réponse : Les points sont approximativement alignés.\n"],
            },
        ],
    )

    responses = extract_responses_from_notebook(notebook)

    assert len(responses) == 2
    assert responses[0].cell_number == 2
    assert responses[0].context == "Loi de la réfraction"
    assert "pente vaut environ 1,5" in responses[0].text
    assert responses[0].word_count > 5
    assert responses[0].is_empty is False

    assert responses[1].cell_number == 4
    assert responses[1].context == "Interprétation"
    assert "approximativement alignés" in responses[1].text


def test_extract_responses_detects_empty_or_placeholder_answers(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Mesure\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** à compléter\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** ?\n"]},
        ],
    )

    responses = extract_responses_from_notebook(notebook)

    assert len(responses) == 3
    assert all(response.is_empty for response in responses)


def test_format_response_extraction_report(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Exploitation\n"]},
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**Réponse :** L'indice obtenu est compatible avec la valeur attendue.\n"],
            },
        ],
    )

    report = format_response_extraction_report(notebook)

    assert "Réponses détectées : 1" in report
    assert "Réponse 1 — cellule 2 — partie « Exploitation »" in report
    assert "Mots :" in report
    assert "compatible avec la valeur attendue" in report


def test_format_response_extraction_report_when_no_response(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Titre\n"]},
            {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": ["print('ok')\n"]},
        ],
    )

    report = format_response_extraction_report(notebook)

    assert "Réponses détectées : 0" in report
    assert "Aucune zone `Réponse :` détectée." in report
