from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from tpstudio.cli import compare_copy_command


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


def test_compare_copy_command_can_export_report(tmp_path: Path, capsys) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.ipynb"
    output = tmp_path / "rapport.txt"

    _write_notebook(
        model,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :**\n\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": ["### Résultat — mesure\n"]},
        ],
    )
    _write_notebook(
        copy,
        [
            {"cell_type": "markdown", "metadata": {}, "source": ["**Réponse :** valeur\n"]},
        ],
    )

    compare_copy_command(
        Namespace(
            model=str(model),
            copy=str(copy),
            output=str(output),
        )
    )

    captured = capsys.readouterr()
    assert "Comparaison modèle / copie" in captured.out
    assert "rapport exporté" in captured.out
    assert output.exists()
    assert "Retour possible à l'étudiant" in output.read_text(encoding="utf-8")
