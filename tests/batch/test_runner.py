import importlib.util
from pathlib import Path
import nbformat
import pytest
from types import SimpleNamespace
import tpstudio.batch.runner as batch_runner
from tpstudio.batch import BatchCopySource, BatchCopyStatus, build_batch_plan, run_snells_laws_batch, sanitize_batch_error_message

def _fixture():
    spec = importlib.util.spec_from_file_location("copy_fixture", Path("tests/orchestration/test_copy_analysis.py")); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def test_two_valid_copies_are_isolated_and_sources_preserved(tmp_path):
    module = _fixture(); paths = []
    for index in (1, 2):
        path = tmp_path / f"copy-{index}.ipynb"; nbformat.write(module._notebook(), path); paths.append(path)
    before = tuple(path.read_bytes() for path in paths)
    plan = build_batch_plan(tuple(BatchCopySource(f"copy-{i:03d}", path) for i, path in enumerate(paths, 1)), tmp_path / "out")
    result = run_snells_laws_batch(plan)
    assert result.success_count == 2 and all(item.status is BatchCopyStatus.SUCCESS for item in result.results)
    assert tuple(path.read_bytes() for path in paths) == before

def test_invalid_notebook_does_not_stop_following_copy(tmp_path):
    module = _fixture(); good = tmp_path / "good.ipynb"; bad = tmp_path / "bad.ipynb"; third = tmp_path / "third.ipynb"
    nbformat.write(module._notebook(), good); bad.write_text("invalid"); nbformat.write(module._notebook(), third)
    plan = build_batch_plan((BatchCopySource("copy-001", good), BatchCopySource("copy-002", bad), BatchCopySource("copy-003", third)), tmp_path / "out")
    result = run_snells_laws_batch(plan)
    assert [item.status for item in result.results] == [BatchCopyStatus.SUCCESS, BatchCopyStatus.FAILED, BatchCopyStatus.SUCCESS]

def test_collision_plan_destinations_are_used_end_to_end(tmp_path):
    module = _fixture(); first_dir = tmp_path / "a"; second_dir = tmp_path / "b"
    first = first_dir / "tp.ipynb"; second = second_dir / "tp.ipynb"
    first_dir.mkdir(); second_dir.mkdir(); nbformat.write(module._notebook(), first); nbformat.write(module._notebook(), second)
    before = first.read_bytes(), second.read_bytes()
    plan = build_batch_plan((BatchCopySource("copy-001", first), BatchCopySource("copy-002", second)), tmp_path / "out")
    result = run_snells_laws_batch(plan)
    assert result.success_count == 2
    names = {path.name for item in result.successful_results for path in (item.notebook_path, item.html_path)}
    assert names == {"copy-001-tp-correction.ipynb", "copy-001-tp-correction.html", "copy-002-tp-correction.ipynb", "copy-002-tp-correction.html"}
    assert not (tmp_path / "out" / "tp-correction.ipynb").exists()
    assert (first.read_bytes(), second.read_bytes()) == before

def test_error_messages_are_sanitized():
    source = BatchCopySource("copy-002", Path("/Users/example/Students/Alice Martin/copie.ipynb"))
    message = sanitize_batch_error_message(ValueError("failed /home/student/private/result.html"), source=source, output_dir=Path("/private/var/out"))
    assert "/Users/" not in message and "/home/" not in message and "/private/" not in message
    assert message == "Échec d'export."

def test_batch_plan_contract_is_exact():
    plan = build_batch_plan((BatchCopySource("copy-001", Path("tests/orchestration/test_copy_analysis.py")),), Path("/tmp/a71g-test"))
    try:
        run_snells_laws_batch(object())
    except TypeError:
        pass
    else:
        raise AssertionError("Le runner doit refuser un objet qui n'est pas BatchPlan.")


def test_unexpected_exception_isolated_and_keyboard_interrupt_propagates(tmp_path, monkeypatch):
    module = _fixture(); paths = []
    for name in ("one", "two", "three"):
        path = tmp_path / f"{name}.ipynb"; nbformat.write(module._notebook(), path); paths.append(path)
    calls = []
    def fake_export(source, output_dir, **kwargs):
        calls.append(source.name)
        if source.name == "two.ipynb":
            raise TypeError("unexpected /Users/private/student.ipynb")
        return SimpleNamespace(
            notebook_artifact=SimpleNamespace(path=kwargs["notebook_output_path"]),
            html_artifact=SimpleNamespace(path=kwargs["html_output_path"]),
            annotation_count=0, limitations=(),
        )
    monkeypatch.setattr(batch_runner, "export_snells_laws_copy", fake_export)
    plan = build_batch_plan(tuple(BatchCopySource(f"copy-{i:03d}", path) for i, path in enumerate(paths, 1)), tmp_path / "out")
    result = run_snells_laws_batch(plan)
    assert [item.status for item in result.results] == [BatchCopyStatus.SUCCESS, BatchCopyStatus.FAILED, BatchCopyStatus.SUCCESS]
    failed = result.results[1]
    assert failed.error_type == "TypeError" and failed.error_message == "Échec d'export."
    assert "/Users/" not in failed.error_message and calls == ["one.ipynb", "two.ipynb", "three.ipynb"]

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt()
    monkeypatch.setattr(batch_runner, "export_snells_laws_copy", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run_snells_laws_batch(build_batch_plan((BatchCopySource("copy-001", paths[0]),), tmp_path / "interrupt"))


def test_stop_on_error_counts_started_and_skipped(tmp_path, monkeypatch):
    module = _fixture(); paths = []
    for name in ("one", "two", "three"):
        path = tmp_path / f"{name}.ipynb"; nbformat.write(module._notebook(), path); paths.append(path)
    calls = []
    def fake_export(source, output_dir, **kwargs):
        calls.append(source.name)
        if source.name == "two.ipynb":
            raise TypeError("unexpected")
        return SimpleNamespace(notebook_artifact=SimpleNamespace(path=kwargs["notebook_output_path"]), html_artifact=SimpleNamespace(path=kwargs["html_output_path"]), annotation_count=0, limitations=())
    monkeypatch.setattr(batch_runner, "export_snells_laws_copy", fake_export)
    options = __import__("tpstudio.batch", fromlist=["BatchOptions"]).BatchOptions(continue_on_error=False)
    plan = build_batch_plan(tuple(BatchCopySource(f"copy-{i:03d}", path) for i, path in enumerate(paths, 1)), tmp_path / "out", options)
    result = run_snells_laws_batch(plan)
    assert result.started_count == 2 and result.success_count == 1 and result.failed_count == 1 and result.skipped_count == 1
    assert [item.status for item in result.results] == [BatchCopyStatus.SUCCESS, BatchCopyStatus.FAILED, BatchCopyStatus.SKIPPED]
    assert calls == ["one.ipynb", "two.ipynb"]


def test_batch_overwrite_is_per_copy(tmp_path):
    module = _fixture(); source = tmp_path / "one.ipynb"; nbformat.write(module._notebook(), source)
    plan = build_batch_plan((BatchCopySource("copy-001", source),), tmp_path / "out")
    assert run_snells_laws_batch(plan).success
    skipped = run_snells_laws_batch(plan)
    assert skipped.skipped_count == 1 and not skipped.success
    overwrite = build_batch_plan((BatchCopySource("copy-001", source),), tmp_path / "out", __import__("tpstudio.batch", fromlist=["BatchOptions"]).BatchOptions(overwrite=True))
    assert run_snells_laws_batch(overwrite).success
