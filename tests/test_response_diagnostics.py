from __future__ import annotations

import json
from pathlib import Path

from tpstudio.response_diagnostics import (
    diagnose_response,
    diagnose_responses_from_notebook,
    format_response_diagnostic_report,
)
from tpstudio.glossary import Glossary, ScientificTerm
from tpstudio.response_extraction import NotebookResponse


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


def test_diagnose_solid_response(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Exploitation\n"]},
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "**Réponse :** La pente vaut environ 1,49. ",
                    "Elle est compatible avec l'indice attendu du plexiglas, proche de 1,5.\n",
                ],
            },
        ],
    )

    diagnoses = diagnose_responses_from_notebook(notebook)

    assert len(diagnoses) == 1
    diagnosis = diagnoses[0]

    assert diagnosis.level == "solide"
    assert diagnosis.has_numeric_value is True
    assert diagnosis.has_comparison is True
    assert diagnosis.has_physical_vocabulary is True
    assert diagnosis.is_vague is False
    assert {"pente", "indice", "plexiglas"} <= set(diagnosis.matched_scientific_terms)
    assert {"quantity", "instrument"} <= set(diagnosis.matched_scientific_categories)
    assert "réponse structurée sur le plan textuel" in diagnosis.signals


def test_diagnose_short_vague_response(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Méthode 2\n"]},
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**Réponse :** Les valeurs sont proches donc c'est correct.\n"],
            },
        ],
    )

    diagnosis = diagnose_responses_from_notebook(notebook)[0]

    assert diagnosis.level == "fragile"
    assert "réponse très courte" in diagnosis.signals
    assert "aucune valeur numérique détectée" in diagnosis.signals
    assert "formulation vague" in diagnosis.signals


def test_diagnose_empty_response(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"

    _write_notebook(
        notebook,
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**Réponse :** à compléter\n"],
            },
        ],
    )

    diagnosis = diagnose_responses_from_notebook(notebook)[0]

    assert diagnosis.level == "à compléter"
    assert "réponse vide ou à compléter" in diagnosis.signals
    assert diagnosis.advice == ["rédiger une réponse complète dans cette zone"]


def test_diagnose_acceptable_response_with_one_weak_signal(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"

    _write_notebook(
        notebook,
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "**Réponse :** La valeur obtenue est compatible avec la valeur attendue ",
                    "car l'écart normalisé est inférieur au seuil choisi.\n",
                ],
            },
        ],
    )

    diagnosis = diagnose_responses_from_notebook(notebook)[0]

    assert diagnosis.level == "acceptable"
    assert "aucune valeur numérique détectée" in diagnosis.signals
    assert "vocabulaire physique peu explicite" not in diagnosis.signals


def test_format_response_diagnostic_report(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Résultat\n"]},
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**Réponse :** Les valeurs sont proches donc la méthode semble correcte.\n"],
            },
        ],
    )

    report = format_response_diagnostic_report(notebook)

    assert "TPStudio - Diagnostic des réponses étudiantes" in report
    assert "Réponses analysées : 1" in report
    assert "Réponse 1 — cellule 2 — partie « Résultat »" in report
    assert "niveau : fragile" in report
    assert "formulation vague" in report
    assert "extrait : Les valeurs sont proches" in report


def test_format_response_diagnostic_report_when_no_response(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"

    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Titre\n"]},
        ],
    )

    report = format_response_diagnostic_report(notebook)

    assert "Réponses analysées : 0" in report
    assert "Aucune zone `Réponse :` détectée." in report


def test_diagnose_response_accepts_a_custom_glossary() -> None:
    response = NotebookResponse(
        cell_number=1,
        context="",
        text="La conductivité mesurée est compatible avec 2,5 S/m.",
        word_count=9,
        is_empty=False,
    )
    glossary = Glossary(
        "electricity",
        "Électricité",
        (ScientificTerm("conductivite", "conductivité", "quantity"),),
    )

    diagnosis = diagnose_response(response, glossary=glossary)

    assert diagnosis.has_physical_vocabulary is True
    assert diagnosis.matched_scientific_terms == ("conductivite",)
    assert diagnosis.matched_scientific_categories == ("quantity",)
