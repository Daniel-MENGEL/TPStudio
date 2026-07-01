from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from tpstudio.cli import feedback_copy_command


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


def test_feedback_copy_command_creates_feedback_notebook(tmp_path: Path, capsys) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"
    output = tmp_path / "copie-avec-retour.ipynb"

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
                "source": ["x = ?\n"],
            },
        ],
    )

    feedback_copy_command(
        Namespace(
            model=str(model),
            copy=str(copy),
            output=str(output),
        )
    )

    captured = capsys.readouterr()

    assert "notebook avec retour créé" in captured.out
    assert output.exists()

    data = json.loads(output.read_text(encoding="utf-8"))
    assert "Retour TPStudio" in "".join(data["cells"][0]["source"])
