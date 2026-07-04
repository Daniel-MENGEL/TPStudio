from __future__ import annotations

from pathlib import Path

from tpstudio.correction_bundle import _append_execution_summary
from tpstudio.notebook_execution import NotebookExecutionResult


def test_execution_summary_mentions_kernel_fallback(tmp_path: Path) -> None:
    report = tmp_path / "rapport.md"
    report.write_text("# Rapport TPStudio\n", encoding="utf-8")

    result = NotebookExecutionResult(
        source=Path("copie.ipynb"),
        output=Path("copie-executed.ipynb"),
        success=True,
        completed=True,
        attempted_code_cells=12,
        total_code_cells=12,
        declared_kernel="conda-base-py",
        used_kernel="python3",
        fallback_used=True,
    )

    _append_execution_summary(report, result)

    text = report.read_text(encoding="utf-8")

    assert "Kernel déclaré par le notebook : conda-base-py" in text
    assert "Kernel utilisé : python3" in text
    assert "Fallback automatique : oui" in text
