from __future__ import annotations

from pathlib import Path

from tpstudio.gradebook_duplicate_summary import (
    append_duplicate_submissions_to_html,
    append_duplicate_submissions_to_markdown,
    duplicate_submissions_output_path,
)
from tpstudio.gradebook_duplicates import DuplicateSubmission


def _duplicate() -> DuplicateSubmission:
    return DuplicateSubmission(
        last_name="DURAND",
        first_name="Alice",
        email="alice.durand@example.test",
        tp_name="Lois de Snell Descartes",
        weeks=("25", "26"),
        notebook_names=("copie-1.ipynb", "copie-2.ipynb"),
    )


def test_duplicate_submissions_output_path() -> None:
    path = duplicate_submissions_output_path(
        Path("Lois-de-Snell-Descartes-semaine-25-suivi.csv")
    )

    assert path == Path("Lois-de-Snell-Descartes-semaine-25-doublons-suspects.csv")


def test_append_duplicate_submissions_to_markdown(tmp_path: Path) -> None:
    path = tmp_path / "bilan.md"
    path.write_text("# Bilan\n", encoding="utf-8")

    append_duplicate_submissions_to_markdown(path, [_duplicate()])

    text = path.read_text(encoding="utf-8")

    assert "## Doublons suspects" in text
    assert "Doublons suspects : 1" in text
    assert "DURAND Alice" in text
    assert "copie-1.ipynb ; copie-2.ipynb" in text


def test_append_duplicate_submissions_to_html(tmp_path: Path) -> None:
    path = tmp_path / "bilan.html"
    path.write_text("<html><body><main><div class=\"grid\"></div></main></body></html>", encoding="utf-8")

    append_duplicate_submissions_to_html(path, [_duplicate()])

    text = path.read_text(encoding="utf-8")

    assert "Doublons suspects" in text
    assert "Doublons suspects : 1" in text
    assert "DURAND" in text
    assert "copie-1.ipynb ; copie-2.ipynb" in text
