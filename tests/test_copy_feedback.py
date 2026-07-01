from __future__ import annotations

import json
from pathlib import Path

from tpstudio.copy_feedback import create_feedback_notebook


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


def test_create_feedback_notebook_inserts_feedback_cell(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"
    output = tmp_path / "copie-retour.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Tracé expérimental\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["x = ?\n"],
            },
        ],
    )

    created = create_feedback_notebook(model, copy, output)

    assert created == output
    data = _read_notebook(output)

    first_cell = data["cells"][0]
    first_source = "".join(first_cell["source"])

    assert first_cell["cell_type"] == "markdown"
    assert "Retour TPStudio" in first_source
    assert "complétez cette cellule puis exécutez-la" in first_source
    assert "Tracé expérimental" in first_source


def test_create_feedback_notebook_is_non_destructive(tmp_path: Path) -> None:
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
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** valeur\n"]},
        ],
    )

    before = copy.read_text(encoding="utf-8")

    created = create_feedback_notebook(model, copy)

    assert created.name == "copie-retour-tpstudio.ipynb"
    assert created.exists()
    assert copy.read_text(encoding="utf-8") == before

    data = _read_notebook(created)
    assert data["cells"][0]["metadata"]["tpstudio"]["cell_role"] == "student_feedback"
    assert data["metadata"]["tpstudio"]["feedback_inserted"] is True


def test_create_feedback_notebook_uses_numbered_name_if_needed(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"
    existing = tmp_path / "copie-retour-tpstudio.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** valeur\n"]},
        ],
    )
    existing.write_text("déjà là", encoding="utf-8")

    created = create_feedback_notebook(model, copy)

    assert created.name == "copie-retour-tpstudio-2.ipynb"
    assert created.exists()
    assert existing.read_text(encoding="utf-8") == "déjà là"
