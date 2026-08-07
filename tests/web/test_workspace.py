from pathlib import Path

import pytest

from tpstudio.web.workspace import WebWorkspace


def test_workspace_materializes_and_resets_without_touching_outside(tmp_path):
    outside = tmp_path / "outside.txt"; outside.write_text("keep")
    with WebWorkspace(tmp_path / "workspace") as workspace:
        first = workspace.materialize("tp.ipynb", b"one", "copy-001")
        second = workspace.materialize("tp.ipynb", b"two", "copy-002")
        assert first.workspace_path != second.workspace_path
        assert first.workspace_path.name == second.workspace_path.name == "tp.ipynb"
        assert first.workspace_path.parent.name == "copy-001"
        assert first.workspace_path.read_bytes() == b"one"
        assert second.workspace_path.parent.name == "copy-002"
        with pytest.raises(ValueError):
            workspace.materialize("../outside.txt", b"bad", "copy-003")
        workspace.reset()
        assert not first.workspace_path.exists() and outside.read_text() == "keep"


def test_workspace_rejects_non_bytes(tmp_path):
    with WebWorkspace(tmp_path / "workspace") as workspace:
        with pytest.raises(TypeError):
            workspace.materialize("tp.ipynb", "not bytes", "copy-001")


def test_replace_selection_reuses_same_selection_and_hashes_content(tmp_path):
    with WebWorkspace(tmp_path / "workspace") as workspace:
        first = workspace.replace_selection((("one.ipynb", b"one"),))[0]
        same = workspace.replace_selection((("one.ipynb", b"one"),))[0]
        changed = workspace.replace_selection((("one.ipynb", b"two"),))[0]
        assert first.workspace_path == same.workspace_path
        assert first.content_sha256 != changed.content_sha256
