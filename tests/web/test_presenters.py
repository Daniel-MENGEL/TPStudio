from pathlib import Path
import pytest

from tpstudio.batch import BatchCopyResult, BatchCopySource, BatchCopyStatus, BatchOptions, BatchRunResult, build_batch_plan
from tpstudio.web.presenters import artifact_download_info, batch_plan_rows, batch_run_rows, has_output_name_collision


def test_presenters_use_planned_basenames_only(tmp_path):
    first = tmp_path / "a" / "tp.ipynb"; second = tmp_path / "b" / "tp.ipynb"
    first.parent.mkdir(); second.parent.mkdir(); first.write_bytes(b"x"); second.write_bytes(b"y")
    plan = build_batch_plan((BatchCopySource("copy-001", first, "tp.ipynb"), BatchCopySource("copy-002", second, "tp.ipynb")), tmp_path / "out", BatchOptions())
    rows = batch_plan_rows(plan)
    assert rows[0].notebook_output_name == "copy-001-tp-correction.ipynb"
    assert all("/" not in value for row in rows for value in (row.original_filename, row.notebook_output_name, row.html_output_name))
    assert has_output_name_collision(plan)
    rows = batch_plan_rows(plan)
    assert rows[0].copy_label == "Copie 1"


def test_batch_run_rows_and_download_info_are_safe(tmp_path):
    notebook = tmp_path / "copy-correction.ipynb"; html = tmp_path / "copy-correction.html"
    notebook.write_text("{}", encoding="utf-8"); html.write_text("<html></html>", encoding="utf-8")
    result = BatchRunResult("project", (
        BatchCopyResult("copy-001", BatchCopyStatus.SUCCESS, notebook, html, 2),
        BatchCopyResult("copy-002", BatchCopyStatus.FAILED, error_type="ValueError", error_message="Notebook invalide."),
        BatchCopyResult("copy-003", BatchCopyStatus.SKIPPED, error_message="Une destination existe déjà."),
    ), tmp_path, 2, 1, 1, 1, 2, 0)
    rows = batch_run_rows(result)
    assert [row.status for row in rows] == ["Réussie", "Échec", "Ignorée"]
    assert rows[0].notebook_output_name == "copy-correction.ipynb"
    assert rows[1].error == "Notebook invalide."
    assert rows[1].problem == "Notebook invalide."
    assert rows[0].problem == "—"
    assert artifact_download_info(result.results[0], tmp_path, "notebook") == ("copy-correction.ipynb", "application/x-ipynb+json", notebook)
    with pytest.raises(ValueError):
        artifact_download_info(BatchCopyResult("x", BatchCopyStatus.SUCCESS, Path("/private/out.ipynb"), html), tmp_path, "notebook")
