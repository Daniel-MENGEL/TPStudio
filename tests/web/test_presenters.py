from pathlib import Path
from dataclasses import replace
import importlib.util
import pytest

from tpstudio.batch import BatchCopyResult, BatchCopySource, BatchCopyStatus, BatchOptions, BatchRunResult, build_batch_plan
from tpstudio.web.presenters import artifact_download_info, batch_plan_rows, batch_run_rows, has_output_name_collision
from tpstudio.reporting import TeacherGraphHeadlineStatus, build_teacher_copy_report
from tpstudio.web.presenters import graph_summary_rows
from tpstudio.web.identity import CopyIdentity, CopyIdentitySource, CopyIdentityStatus


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


def test_batch_plan_rows_label_reference_notebooks_instead_of_students(tmp_path):
    first = tmp_path / "correction.ipynb"
    second = tmp_path / "statement.ipynb"
    first.write_bytes(b"x")
    second.write_bytes(b"y")
    plan = build_batch_plan(
        (
            BatchCopySource("copy-001", first, first.name),
            BatchCopySource("copy-002", second, second.name),
        ),
        tmp_path / "out",
        BatchOptions(),
    )
    identities = {
        "copy-001": CopyIdentity(
            (), CopyIdentitySource.NOTEBOOK,
            CopyIdentityStatus.REFERENCE_CORRECTION, "Corrigé",
        ),
        "copy-002": CopyIdentity(
            (), CopyIdentitySource.NOTEBOOK,
            CopyIdentityStatus.EMPTY_STATEMENT, "Énoncé vide",
        ),
    }
    rows = batch_plan_rows(plan, identities)
    assert [row.students_display for row in rows] == ["Corrigé", "Énoncé vide"]
    assert [row.identity_status for row in rows] == ["Référence", "Référence"]


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


def _teacher_report(tmp_path):
    path = Path("tests/orchestration/test_copy_analysis.py")
    spec = importlib.util.spec_from_file_location("copy_fixture_for_presenters", path)
    module = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(module)
    return build_teacher_copy_report(module._analyze(tmp_path))


def test_graph_summary_rows_are_pure_and_map_icons(tmp_path):
    report = _teacher_report(tmp_path)
    base = report.regression_graphs[0]
    summaries = tuple(
        replace(base, regression_id=f"regression-{index}", headline_status=status,
                headline_text=f"Titre {status.value}", summary_lines=(f"Ligne {index}",),
                technical_details=(f"Détail {index}",), requires_human_review=status is TeacherGraphHeadlineStatus.REVIEW)
        for index, status in enumerate(TeacherGraphHeadlineStatus, 1)
    )
    rows = graph_summary_rows(replace(report, regression_graphs=summaries), key_prefix="copy-a")
    assert [row.icon for row in rows] == ["✅", "⚠️", "❌", "ℹ️"]
    assert [row.headline for row in rows] == [f"Titre {status.value}" for status in TeacherGraphHeadlineStatus]
    assert rows[1].requires_human_review is True
    assert rows[0].summary_lines == ("Ligne 1",)
    assert rows[0].technical_details == ("Détail 1",)
    assert len({row.stable_key for row in rows}) == 4
    assert all("CONSISTENT" not in row.headline for row in rows)
    assert report.regression_graphs == (base,)


def test_graph_summary_rows_none_empty_order_and_prefix(tmp_path):
    report = _teacher_report(tmp_path)
    assert graph_summary_rows(None) == ()
    assert graph_summary_rows(replace(report, regression_graphs=())) == ()
    first = graph_summary_rows(report, key_prefix="copy-a")[0]
    second = graph_summary_rows(report, key_prefix="copy-b")[0]
    assert first.stable_key != second.stable_key
    assert first.stable_key.startswith("graph-summary-copy-a-")
