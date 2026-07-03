from __future__ import annotations

import json
from pathlib import Path

import pytest

from tpstudio.correction_bundle import correct_copy


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


def _model_cell() -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": ["**Réponse :**\n\n"],
    }


def _student_cell(text: str = "L'indice mesuré vaut 1,49.") -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [f"**Réponse :** {text}\n"],
    }


def test_correct_copy_creates_notebook_and_markdown_report(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "Alice-Durand.ipynb"
    output_dir = tmp_path / "corrections"

    _write_notebook(model, [_model_cell()])
    _write_notebook(copy, [_student_cell()])

    original = copy.read_text(encoding="utf-8")

    paths = correct_copy(
        model,
        copy,
        output_dir=output_dir,
    )

    assert paths.notebook == output_dir / "Alice-Durand-correction.ipynb"
    assert paths.markdown_report == output_dir / "Alice-Durand-correction.md"

    assert paths.notebook.exists()
    assert paths.markdown_report.exists()
    assert copy.read_text(encoding="utf-8") == original

    corrected = json.loads(paths.notebook.read_text(encoding="utf-8"))
    assert "Retour TPStudio" in "".join(corrected["cells"][0]["source"])

    report = paths.markdown_report.read_text(encoding="utf-8")
    assert "# Rapport TPStudio" in report


def test_correct_copy_refuses_to_overwrite_existing_outputs(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "Alice-Durand.ipynb"
    output_dir = tmp_path / "corrections"

    _write_notebook(model, [_model_cell()])
    _write_notebook(copy, [_student_cell()])
    output_dir.mkdir()

    existing = output_dir / "Alice-Durand-correction.ipynb"
    existing.write_text("à conserver", encoding="utf-8")

    with pytest.raises(FileExistsError, match="--overwrite"):
        correct_copy(
            model,
            copy,
            output_dir=output_dir,
        )

    assert existing.read_text(encoding="utf-8") == "à conserver"
    assert not (output_dir / "Alice-Durand-correction.md").exists()


def test_correct_copy_overwrite_replaces_existing_outputs(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "Alice-Durand.ipynb"
    output_dir = tmp_path / "corrections"

    _write_notebook(model, [_model_cell()])
    _write_notebook(copy, [_student_cell("Réponse suffisamment développée.")])
    output_dir.mkdir()

    notebook_output = output_dir / "Alice-Durand-correction.ipynb"
    report_output = output_dir / "Alice-Durand-correction.md"

    notebook_output.write_text("ancien notebook", encoding="utf-8")
    report_output.write_text("ancien rapport", encoding="utf-8")

    paths = correct_copy(
        model,
        copy,
        output_dir=output_dir,
        overwrite=True,
    )

    assert paths.notebook.read_text(encoding="utf-8") != "ancien notebook"
    assert paths.markdown_report.read_text(encoding="utf-8") != "ancien rapport"


def test_correct_copy_rejects_non_notebook_input(tmp_path: Path) -> None:
    model = tmp_path / "modele.ipynb"
    copy = tmp_path / "copie.txt"

    _write_notebook(model, [_model_cell()])
    copy.write_text("pas un notebook", encoding="utf-8")

    with pytest.raises(ValueError, match=".ipynb"):
        correct_copy(
            model,
            copy,
            output_dir=tmp_path / "corrections",
        )
