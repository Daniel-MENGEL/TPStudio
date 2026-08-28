from __future__ import annotations

import json
from pathlib import Path

from tpstudio.copy_comparison import compare_copy_to_model
from tpstudio.feedback_report import (
    export_feedback_report,
    format_feedback_report_markdown,
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


def test_format_feedback_report_markdown_contains_feedback_sections(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

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
                "source": ["**Réponse :** L'indice mesuré vaut 1,49, compatible avec l'indice attendu du plexiglas.\n"],
            },
        ],
    )

    comparison = compare_copy_to_model(model, copy)
    markdown = format_feedback_report_markdown(comparison)

    assert markdown.startswith("# Rapport TPStudio")
    assert "Modèle : `modele.ipynb`" in markdown
    assert "Copie : `copie.ipynb`" in markdown
    assert "## Retour automatique" in markdown
    assert "## Retour TPStudio" not in markdown
    assert "### Synthèse rapide" in markdown
    assert "### Diagnostic des réponses" in markdown
    assert "Corrigeabilité globale" in markdown


def test_export_feedback_report_writes_markdown_file(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"
    output = tmp_path / "rapport.md"

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

    created = export_feedback_report(model, copy, output)

    assert created == output
    assert output.exists()

    text = output.read_text(encoding="utf-8")
    assert "# Rapport TPStudio" in text
    assert "Réponses analysées" in text


def test_export_feedback_report_uses_numbered_name_if_needed(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"
    existing = tmp_path / "copie-rapport-tpstudio.md"

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
                "source": ["**Réponse :** L'indice 1,49 est compatible avec l'indice attendu du plexiglas.\n"],
            },
        ],
    )
    existing.write_text("déjà là", encoding="utf-8")

    created = export_feedback_report(model, copy)

    assert created.name == "copie-rapport-tpstudio-2.md"
    assert created.exists()
    assert existing.read_text(encoding="utf-8") == "déjà là"
