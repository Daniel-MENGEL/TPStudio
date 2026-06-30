from __future__ import annotations

import json
from pathlib import Path

from tpstudio.student_inspection import (
    format_student_notebook_report,
    inspect_student_notebook,
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


def test_student_inspection_counts_response_cells(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"
    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["## Partie 1\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\nLa valeur mesurée est correcte.\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
        ],
    )

    diagnostic = inspect_student_notebook(notebook)

    assert diagnostic.total_cells == 3
    assert diagnostic.markdown_cells == 3
    assert diagnostic.response_cells == 2
    assert diagnostic.filled_response_cells == 1
    assert diagnostic.empty_response_cells == 1
    assert diagnostic.headings == 1


def test_student_inspection_counts_code_execution_state(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"
    _write_notebook(
        notebook,
        [
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [{"output_type": "stream", "text": ["ok\n"]}],
                "source": ["print('ok')\n"],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["x = 1\n"],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 2,
                "outputs": [{"output_type": "error", "ename": "ValueError"}],
                "source": ["raise ValueError()\n"],
            },
        ],
    )

    diagnostic = inspect_student_notebook(notebook)

    assert diagnostic.code_cells == 3
    assert diagnostic.code_cells_with_outputs == 2
    assert diagnostic.code_cells_without_outputs == 1
    assert diagnostic.code_cells_not_executed == 1
    assert diagnostic.code_cells_with_errors == 1


def test_student_inspection_formats_report(tmp_path: Path) -> None:
    notebook = tmp_path / "copie.ipynb"
    _write_notebook(
        notebook,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\nÀ compléter\n"]},
        ],
    )

    diagnostic = inspect_student_notebook(notebook)
    report = format_student_notebook_report(diagnostic)

    assert "Inspection de copie" in report
    assert "réponses vides ou à compléter : 1" in report
