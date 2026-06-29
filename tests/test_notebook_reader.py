from __future__ import annotations

import json

from tpstudio.readers import NotebookReader


def test_notebook_reader_counts_cells(tmp_path):
    notebook_path = tmp_path / "tp.ipynb"
    notebook_data = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["# Titre\n", "Réponse : expliquer."],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": ["x = 1\n"],
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    notebook_path.write_text(
        json.dumps(notebook_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    notebook = NotebookReader(notebook_path).parse()

    assert notebook.path == notebook_path
    assert notebook.cell_count == 2
    assert notebook.markdown_cell_count == 1
    assert notebook.code_cell_count == 1
    assert notebook.response_cell_count == 1
    assert notebook.cells[0].source.startswith("# Titre")
