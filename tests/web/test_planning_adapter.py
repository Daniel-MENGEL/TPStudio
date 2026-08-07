from pathlib import Path

import nbformat
import pytest
from hashlib import sha256

from tpstudio.batch import BatchOptions
from tpstudio.web.model import SelectedCopy, WebBatchOptions
from tpstudio.web.planning import build_batch_plan_from_web_selection


def _copy(tmp_path, source_id, name):
    path = tmp_path / f"{source_id}-{name}"; nbformat.write(nbformat.v4.new_notebook(), path)
    return SelectedCopy(source_id, name, path, sha256(path.read_bytes()).hexdigest())


def test_adapter_builds_batch_plan_and_preserves_planned_outputs(tmp_path):
    copies = (_copy(tmp_path, "copy-001", "tp.ipynb"), _copy(tmp_path, "copy-002", "tp.ipynb"))
    plan = build_batch_plan_from_web_selection(copies, tmp_path / "out", WebBatchOptions(overwrite=True, hide_code=True))
    assert isinstance(plan.options, BatchOptions)
    assert plan.options.overwrite and plan.options.hide_code
    assert plan.planned_outputs[0].notebook_path.name == "copy-001-tp-correction.ipynb"
    assert plan.planned_outputs[1].html_path.name == "copy-002-tp-correction.html"


def test_adapter_does_not_run_batch(tmp_path):
    with pytest.raises(ValueError, match="Aucune"):
        build_batch_plan_from_web_selection((), tmp_path / "out")


def test_original_basenames_drive_a71g_names(tmp_path):
    from tpstudio.web.workspace import WebWorkspace
    import nbformat
    valid = nbformat.writes(nbformat.v4.new_notebook()).encode()
    with WebWorkspace(tmp_path / "workspace") as workspace:
        copies = workspace.replace_selection((("one.ipynb", valid), ("two.ipynb", valid)))
        plan = build_batch_plan_from_web_selection(copies, tmp_path / "out")
        assert [item.notebook_path.name for item in plan.planned_outputs] == ["one-correction.ipynb", "two-correction.ipynb"]


def test_duplicate_original_basenames_are_disambiguated_by_a71g(tmp_path):
    from tpstudio.web.workspace import WebWorkspace
    import nbformat
    valid = nbformat.writes(nbformat.v4.new_notebook()).encode()
    with WebWorkspace(tmp_path / "workspace") as workspace:
        copies = workspace.replace_selection((("tp.ipynb", valid), ("tp.ipynb", valid + b" ")))
        plan = build_batch_plan_from_web_selection(copies, tmp_path / "out")
        assert [item.notebook_path.name for item in plan.planned_outputs] == ["copy-001-tp-correction.ipynb", "copy-002-tp-correction.ipynb"]


def test_invalid_notebook_is_rejected_before_plan(tmp_path):
    from tpstudio.web.workspace import WebWorkspace
    with WebWorkspace(tmp_path / "workspace") as workspace:
        copies = workspace.replace_selection((("bad.ipynb", b"not json"),))
        with pytest.raises(ValueError, match="Notebook invalide"):
            build_batch_plan_from_web_selection(copies, tmp_path / "out")
