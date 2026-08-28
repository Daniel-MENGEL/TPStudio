from pathlib import Path
from types import SimpleNamespace
import importlib.util

import pytest

from tpstudio.batch import BatchCopyResult, BatchCopySource, BatchCopyStatus, BatchOptions, BatchRunResult, build_batch_plan
from tpstudio.web.execution import can_run_batch, export_output_stem, run_prepared_batch
from tpstudio.web.identity import CopyIdentity, CopyIdentityStatus, StudentIdentity
from tpstudio.web.presenters import identity_resolution_candidates
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


def test_generic_export_name_uses_project_and_confirmed_students(tmp_path):
    identity = CopyIdentity(
        (StudentIdentity("Jules BERNARD"), StudentIdentity("Daniel MENGEL")),
        None,
        CopyIdentityStatus.CONFIRMED,
    )
    analysis = SimpleNamespace(
        project=SimpleNamespace(
            identity=SimpleNamespace(title="Premières mesures au labo")
        ),
        source=SimpleNamespace(
            path=tmp_path / "copie.ipynb",
            display_name="copie.ipynb",
        ),
    )
    stem = export_output_stem(analysis, identity)
    assert stem == (
        "Premières-mesures-au-labo-Jules-BERNARD-Daniel-MENGEL-Correction"
    )


def test_generic_export_name_fallback_does_not_duplicate_correction(tmp_path):
    source = tmp_path / "Premieres-mesures-au-labo-Corrige.ipynb"
    source.write_text("{}", encoding="utf-8")
    analysis = SimpleNamespace(
        project=SimpleNamespace(identity=SimpleNamespace(title="Premières mesures au labo")),
        source=SimpleNamespace(path=source, display_name=source.name),
    )
    assert export_output_stem(analysis) == "Premieres-mesures-au-labo-Corrige"


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


def test_manual_identity_confirmation_unlocks_batch_and_candidates_are_deduplicated(tmp_path):
    from tpstudio.web.identity import CopyIdentitySource, confirm_copy_identity
    def plan_for(items):
        return build_batch_plan(
            tuple(BatchCopySource(item.source_id, item.workspace_path, item.original_filename) for item in items),
            tmp_path / "out",
        )
    first = _copy(tmp_path, "copy-001", CopyIdentity(
        (StudentIdentity("Jules BERNARD"), StudentIdentity("Daniel MENGEL")),
        CopyIdentitySource.FILENAME, CopyIdentityStatus.TO_REVIEW,
    ))
    second = _copy(tmp_path, "copy-002", CopyIdentity(
        (StudentIdentity("Jules BERNARD"),), CopyIdentitySource.FILENAME,
        CopyIdentityStatus.TO_REVIEW,
    ))
    assert [student.display_name for student in identity_resolution_candidates((first, second))] == ["Daniel MENGEL", "Jules BERNARD"]
    confirmed = confirm_copy_identity(first, (StudentIdentity("Jules BERNARD"), StudentIdentity("Daniel MENGEL")))
    assert can_run_batch((confirmed, second), plan_for((confirmed, second)))[0] is False
    confirmed_second = confirm_copy_identity(second, (StudentIdentity("Jules BERNARD"), StudentIdentity("Daniel MENGEL")))
    assert can_run_batch((confirmed, confirmed_second), plan_for((confirmed, confirmed_second)))[0] is True


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
    assert "tpstudio-severity-" in result.results[0].notebook_path.read_text(encoding="utf-8")
    assert "tpstudio-severity-" in result.results[0].html_path.read_text(encoding="utf-8")


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
