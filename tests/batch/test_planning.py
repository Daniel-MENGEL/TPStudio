from pathlib import Path
import nbformat
import pytest
from tpstudio.batch import BatchCopySource, build_batch_plan

def _source(path, source_id):
    path.parent.mkdir(parents=True, exist_ok=True); nbformat.write(nbformat.v4.new_notebook(), path)
    return BatchCopySource(source_id, path)

def test_plan_single_and_collision_disambiguation(tmp_path):
    one = _source(tmp_path / "a" / "tp.ipynb", "copy-001"); two = _source(tmp_path / "b" / "tp.ipynb", "copy-002")
    plan = build_batch_plan((one, two), tmp_path / "out")
    assert plan.planned_outputs[0].notebook_path.name == "copy-001-tp-correction.ipynb"
    assert plan.planned_outputs[1].html_path.name == "copy-002-tp-correction.html"

def test_plan_rejects_duplicate_ids_paths_and_unsafe_ids(tmp_path):
    one = _source(tmp_path / "a.ipynb", "copy-001")
    with pytest.raises(ValueError): build_batch_plan((one, BatchCopySource("copy-001", tmp_path / "b.ipynb")), tmp_path / "out")
    with pytest.raises(ValueError): build_batch_plan((one, BatchCopySource("../bad", one.path)), tmp_path / "out")

def test_existing_destination_is_left_for_runner_policy(tmp_path):
    one = _source(tmp_path / "tp.ipynb", "copy-001"); out = tmp_path / "out"; out.mkdir()
    (out / "tp-correction.html").write_text("old")
    plan = build_batch_plan((one,), out)
    assert plan.planned_outputs[0].html_path.exists()


def test_plan_without_output_stem_keeps_historical_names(tmp_path):
    source = _source(tmp_path / "tp.ipynb", "copy-001")
    plan = build_batch_plan((source,), tmp_path / "out")
    assert plan.planned_outputs[0].notebook_path.name == "tp-correction.ipynb"
    assert plan.planned_outputs[0].html_path.name == "tp-correction.html"


def test_plan_uses_output_stem_and_disambiguates_equal_stems(tmp_path):
    stem = "Lois-de-Snell-Descartes-Jules-BERNARD-Daniel-MENGEL"
    one = _source(tmp_path / "a.ipynb", "copy-001")
    two = _source(tmp_path / "b.ipynb", "copy-002")
    one = BatchCopySource(one.source_id, one.path, output_stem=stem)
    two = BatchCopySource(two.source_id, two.path, output_stem=stem)
    plan = build_batch_plan((one, two), tmp_path / "out")
    names = [(item.notebook_path.name, item.html_path.name) for item in plan.planned_outputs]
    assert names == [
        (f"copy-001-{stem}-correction.ipynb", f"copy-001-{stem}-correction.html"),
        (f"copy-002-{stem}-correction.ipynb", f"copy-002-{stem}-correction.html"),
    ]
    assert len({name for pair in names for name in pair}) == 4
