from pathlib import Path
from types import SimpleNamespace
import importlib.util

import pytest

from tpstudio.batch import BatchCopyResult, BatchCopySource, BatchCopyStatus, BatchOptions, BatchRunResult, build_batch_plan
from tpstudio.web.execution import can_run_batch, run_prepared_batch
from tpstudio.web.identity import CopyIdentity, CopyIdentityStatus, StudentIdentity
from tpstudio.web.model import SelectedCopy


def _copy(tmp_path, source_id, identity):
    path = tmp_path / f"{source_id}.ipynb"
    path.write_text("{}", encoding="utf-8")
    return SelectedCopy(source_id, path.name, path, "a" * 64, identity)


def _identity(status):
    students = (StudentIdentity("Jules BERNARD"),) if status is CopyIdentityStatus.CONFIRMED else ()
    return CopyIdentity(students, None, status)


def test_can_run_requires_confirmed_identities_and_plan(tmp_path):
    source = tmp_path / "copy.ipynb"
    source.write_text("{}", encoding="utf-8")
    plan = build_batch_plan((BatchCopySource("copy-001", source),), tmp_path / "out", BatchOptions())
    confirmed = _copy(tmp_path, "copy-001", _identity(CopyIdentityStatus.CONFIRMED))
    review = _copy(tmp_path, "copy-001", _identity(CopyIdentityStatus.TO_REVIEW))
    missing = _copy(tmp_path, "copy-001", _identity(CopyIdentityStatus.MISSING))
    assert can_run_batch((confirmed,), plan)[0]
    assert not can_run_batch((review,), plan)[0]
    assert not can_run_batch((missing,), plan)[0]
    assert not can_run_batch((confirmed,), None)[0]


def test_run_prepared_batch_delegates_to_a71g(monkeypatch, tmp_path):
    source = tmp_path / "copy.ipynb"; source.write_text("{}", encoding="utf-8")
    plan = build_batch_plan((BatchCopySource("copy-001", source),), tmp_path / "out")
    expected = BatchRunResult("project", (BatchCopyResult("copy-001", BatchCopyStatus.SKIPPED, error_message="test"),), tmp_path / "out", 0, 0, 0, 1, 0, 0)
    calls = []
    monkeypatch.setattr("tpstudio.web.execution.run_snells_laws_batch", lambda received: calls.append(received) or expected)
    assert run_prepared_batch(plan) is expected
    assert calls == [plan]


def test_run_prepared_batch_rejects_non_plan():
    with pytest.raises(TypeError):
        run_prepared_batch(object())


def test_real_partial_filename_keeps_confirmed_identity_and_canonical_stem(tmp_path):
    import nbformat
    from tpstudio.web.identity import identify_selected_copy, build_canonical_copy_stem, canonical_tp_name
    from tpstudio.web.planning import build_batch_plan_from_web_selection
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("**Noms :** Jules BERNARD et Daniel MENGEL")])
    path = tmp_path / "Lois-de-Snell-Descartes-Daniel et Jules.ipynb"
    nbformat.write(notebook, path)
    selected = SelectedCopy("copy-001", path.name, path, "a" * 64)
    identified = identify_selected_copy(selected)
    assert identified.identity.status is CopyIdentityStatus.CONFIRMED
    plan = build_batch_plan_from_web_selection((identified,), tmp_path / "out")
    assert plan.sources[0].output_stem == "Lois-de-Snell-Descartes-Jules-BERNARD-Daniel-MENGEL"
    assert can_run_batch((identified,), plan)[0]
    assert plan.planned_outputs[0].notebook_path.name == "Lois-de-Snell-Descartes-Jules-BERNARD-Daniel-MENGEL-correction.ipynb"
    assert plan.planned_outputs[0].html_path.name == "Lois-de-Snell-Descartes-Jules-BERNARD-Daniel-MENGEL-correction.html"


def test_run_prepared_batch_real_vertical_preserves_source(tmp_path):
    spec = importlib.util.spec_from_file_location("copy_fixture", Path("tests/orchestration/test_copy_analysis.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    source = tmp_path / "copy.ipynb"
    import nbformat
    nbformat.write(module._notebook(), source)
    before = source.read_bytes()
    plan = build_batch_plan((BatchCopySource("copy-001", source),), tmp_path / "out", BatchOptions())
    result = run_prepared_batch(plan)
    assert result.success and result.results[0].notebook_path.exists() and result.results[0].html_path.exists()
    assert source.read_bytes() == before


def test_run_prepared_batch_real_vertical_isolates_invalid_copy(tmp_path):
    spec = importlib.util.spec_from_file_location("copy_fixture", Path("tests/orchestration/test_copy_analysis.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    import nbformat
    paths = []
    for source_id in ("copy-001", "copy-002", "copy-003"):
        path = tmp_path / f"{source_id}.ipynb"
        if source_id == "copy-002":
            path.write_text("invalid", encoding="utf-8")
        else:
            nbformat.write(module._notebook(), path)
        paths.append(path)
    plan = build_batch_plan(tuple(BatchCopySource(f"copy-{index:03d}", path) for index, path in enumerate(paths, 1)), tmp_path / "out")
    result = run_prepared_batch(plan)
    assert [item.status for item in result.results] == [BatchCopyStatus.SUCCESS, BatchCopyStatus.FAILED, BatchCopyStatus.SUCCESS]


def test_real_vertical_repairs_legacy_cell_ids_without_writing_source(tmp_path):
    import json
    import nbformat
    spec = importlib.util.spec_from_file_location("copy_fixture", Path("tests/orchestration/test_copy_analysis.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    payload = json.loads(nbformat.writes(module._notebook()))
    for cell in payload["cells"]:
        cell["id"] = ""
    source = tmp_path / "legacy.ipynb"
    source.write_text(json.dumps(payload), encoding="utf-8")
    before = source.read_bytes()
    plan = build_batch_plan((BatchCopySource("copy-001", source),), tmp_path / "out", BatchOptions())
    result = run_prepared_batch(plan)
    assert result.success and source.read_bytes() == before


def test_real_vertical_preserves_legacy_v44_schema_for_annotations(tmp_path):
    import json
    import nbformat
    spec = importlib.util.spec_from_file_location("copy_fixture", Path("tests/orchestration/test_copy_analysis.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    payload = json.loads(nbformat.writes(module._notebook()))
    payload["nbformat_minor"] = 4
    for cell in payload["cells"]:
        cell.pop("id", None)
    source = tmp_path / "legacy-v44.ipynb"
    source.write_text(json.dumps(payload), encoding="utf-8")
    before = source.read_bytes()
    plan = build_batch_plan((BatchCopySource("copy-001", source),), tmp_path / "out", BatchOptions())
    result = run_prepared_batch(plan)
    assert result.success
    assert source.read_bytes() == before
