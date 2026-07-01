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
    assert "À corriger avant de rendre" in first_source
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
    assert data["cells"][0]["metadata"]["tpstudio"]["format"] == "structured_v3"
    assert data["metadata"]["tpstudio"]["feedback_inserted"] is True
    assert data["metadata"]["tpstudio"]["feedback_format"] == "structured_v3"


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


def test_structured_feedback_markdown_has_readable_sections(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["### Résultat — mesure\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["### Interprétation\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["### Checklist finale\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Mesure\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["x = ?\n"],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["import numpy as np\n"],
            },
        ],
    )

    comparison = compare_copy_to_model(model, copy)
    markdown = structured_feedback_markdown(comparison)

    assert "### Bilan rapide" in markdown
    assert "### À corriger avant de rendre" in markdown
    assert "### À vérifier" in markdown
    assert "### Commentaires dans le notebook" in markdown
    assert "### Conseil avant nouveau rendu" in markdown
    assert "Niveau de corrigeabilité" in markdown
    assert "Commentaires locaux insérés" in markdown
    assert "Cellule 2 — partie « Mesure »" in markdown
    assert "complétez cette cellule puis exécutez-la" in markdown
    assert "Cellule 3 — partie « Mesure »" not in markdown
    assert "Certains résultats attendus" in markdown
    assert "Certaines interprétations attendues" in markdown


def test_structured_feedback_markdown_mentions_no_blocking_issue_when_clean(tmp_path: Path) -> None:
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
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** réponse rédigée\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [{"output_type": "stream", "text": ["ok\n"]}],
                "source": ["print('ok')\n"],
            },
        ],
    )

    comparison = compare_copy_to_model(model, copy)
    markdown = structured_feedback_markdown(comparison)

    assert "Aucun point bloquant évident détecté" in markdown
    assert "Le notebook semble techniquement exploitable" in markdown


def test_local_feedback_comments_are_inserted_after_target_cells(tmp_path: Path) -> None:
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
            {"cell_type": "markdown", "metadata": {}, "source": ["## Mesure\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["x = ?\n"],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["import numpy as np\n"],
            },
        ],
    )

    created = create_feedback_notebook(model, copy, output)
    data = _read_notebook(created)
    cells = data["cells"]

    assert "Retour TPStudio" in "".join(cells[0]["source"])

    local_feedback_cells = [
        cell for cell in cells
        if cell.get("metadata", {}).get("tpstudio", {}).get("cell_role") == "local_feedback"
    ]

    assert len(local_feedback_cells) == 1

    local_source = "".join(local_feedback_cells[0]["source"])

    assert "cellule contient encore du code à compléter" in local_source
    assert "n'a pas été exécutée" in local_source

    local_index = cells.index(local_feedback_cells[0])
    assert "x = ?" in "".join(cells[local_index - 1]["source"])


def test_local_feedback_by_cell_combines_multiple_issues(tmp_path: Path) -> None:
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
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [{"output_type": "error", "ename": "SyntaxError"}],
                "source": ["x = ?\n"],
            },
        ],
    )

    comparison = compare_copy_to_model(model, copy)
    comments = local_feedback_by_cell(comparison)

    assert 1 in comments
    assert len(comments[1]) == 2
    assert any("code à compléter" in comment for comment in comments[1])
    assert any("erreur d'exécution" in comment for comment in comments[1])


def test_setup_only_cells_do_not_get_local_feedback(tmp_path: Path) -> None:
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
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "import numpy as np\n",
                    "import matplotlib.pyplot as plt\n",
                    "plt.rcParams.update({\n",
                    "    'figure.figsize': (7, 4.5),\n",
                    "})\n",
                ],
            },
        ],
    )

    comparison = compare_copy_to_model(model, copy)
    comments = local_feedback_by_cell(comparison)
    markdown = structured_feedback_markdown(comparison)

    assert comments == {}
    assert "cellule de code à exécuter" not in markdown
