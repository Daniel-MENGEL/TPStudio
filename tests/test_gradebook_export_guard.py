from __future__ import annotations

from tpstudio.gradebook_check import GradebookCheckSummary
from tpstudio.gradebook_export_guard import (
    format_gradebook_export_blocked_message,
    gradebook_check_has_blocking_issues,
)


def _summary(
    *,
    unmatched_named_students: int = 0,
    missing_identity_notebooks: int = 0,
    missing_students: int = 0,
) -> GradebookCheckSummary:
    return GradebookCheckSummary(
        tp_name="Lois de Snell Descartes",
        session="Séance n°2",
        kholle_week="25",
        pattern="*.ipynb",
        notebooks_found=2,
        notebooks_analyzed=2,
        notebooks_ignored=0,
        gradebook_rows=2,
        detected_students=2,
        unmatched_named_students=unmatched_named_students,
        missing_identity_notebooks=missing_identity_notebooks,
        missing_students=missing_students,
    )


def test_gradebook_check_has_no_blocking_issues_when_clean() -> None:
    assert gradebook_check_has_blocking_issues(_summary()) is False


def test_gradebook_check_does_not_block_missing_students() -> None:
    assert gradebook_check_has_blocking_issues(_summary(missing_students=4)) is False


def test_gradebook_check_blocks_unmatched_names() -> None:
    assert gradebook_check_has_blocking_issues(_summary(unmatched_named_students=1)) is True


def test_gradebook_check_blocks_missing_identities() -> None:
    assert gradebook_check_has_blocking_issues(_summary(missing_identity_notebooks=1)) is True


def test_format_blocked_message() -> None:
    text = format_gradebook_export_blocked_message(_summary(unmatched_named_students=1))

    assert "Contrôle TPStudio du suivi" in text
    assert "Export interrompu" in text
    assert "noms non reconnus ou identités absentes" in text
    assert "rapports non rendus" in text
    assert "--allow-issues" in text
