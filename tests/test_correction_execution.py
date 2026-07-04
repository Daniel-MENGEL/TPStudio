from __future__ import annotations

import json
from pathlib import Path

from tpstudio.correction_bundle import correct_copy
from tpstudio.notebook_execution import NotebookExecutionResult


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


def test_correct_copy_execute_first_uses_temporary_executed_copy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "Alice-Durand.ipynb"
    output_dir = tmp_path / "corrections"

    _write_notebook(
        model,
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**Réponse :**\n"],
            }
        ],
    )
    _write_notebook(
        copy,
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**Réponse :** Une réponse correcte.\n"],
            }
        ],
    )

    original = copy.read_text(encoding="utf-8")

    def fake_execute(source, output, **kwargs):
        output.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return NotebookExecutionResult(
            source=source,
            output=output,
            success=True,
            completed=True,
            attempted_code_cells=2,
            total_code_cells=2,
        )

    monkeypatch.setattr(
        "tpstudio.correction_bundle.execute_notebook_copy",
        fake_execute,
    )

    paths = correct_copy(
        model,
        copy,
        output_dir=output_dir,
        execute_first=True,
        cell_timeout=30,
    )

    assert copy.read_text(encoding="utf-8") == original
    assert paths.notebook.exists()
    assert paths.markdown_report.exists()
    assert paths.execution is not None
    assert paths.execution.success is True
    assert paths.execution.output == paths.notebook

    report = paths.markdown_report.read_text(encoding="utf-8")
    assert "## Exécution préalable" in report
    assert "Cellules code tentées : 2/2" in report
