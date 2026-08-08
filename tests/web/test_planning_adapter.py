from pathlib import Path

import nbformat
import pytest
from hashlib import sha256

from tpstudio.batch import BatchOptions
from tpstudio.web.model import SelectedCopy, WebBatchOptions
from tpstudio.web.planning import build_batch_plan_from_web_selection, resolve_output_dir, WebInputError


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


def test_output_dir_expands_tilde_and_rejects_files(tmp_path):
    assert resolve_output_dir("~/Documents/Sup/TP/Notebooks-corrigés").is_absolute()
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(WebInputError, match="invalide"):
        resolve_output_dir(str(file_path))
    with pytest.raises(WebInputError, match="vide"):
        resolve_output_dir("   ")


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


def test_web_validation_uses_the_same_no_convert_contract_as_a71(tmp_path):
    from tpstudio.web.planning import validate_selected_notebook
    from tpstudio.orchestration import NotebookCopySource, load_notebook_copy
    import nbformat
    path = tmp_path / "copy.ipynb"
    nbformat.write(nbformat.v4.new_notebook(), path)
    selected = _copy(tmp_path, "copy-001", path.name)
    validate_selected_notebook(selected)
    loaded = load_notebook_copy(NotebookCopySource("copy-001", path.name, path))
    assert loaded.nbformat == nbformat.read(path, as_version=nbformat.NO_CONVERT).nbformat


def test_confirmed_notebook_identity_drives_canonical_output_stem(tmp_path):
    from tpstudio.web.workspace import WebWorkspace
    import nbformat
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("Noms : Jules BERNARD et Daniel MENGEL")])
    content = nbformat.writes(notebook).encode()
    with WebWorkspace(tmp_path / "workspace") as workspace:
        copies = workspace.replace_selection((("tp.ipynb", content),))
        plan = build_batch_plan_from_web_selection(copies, tmp_path / "out")
    assert plan.sources[0].output_stem == "Lois-de-Snell-Descartes-Jules-BERNARD-Daniel-MENGEL"
    assert plan.planned_outputs[0].notebook_path.name == "Lois-de-Snell-Descartes-Jules-BERNARD-Daniel-MENGEL-correction.ipynb"
    assert plan.planned_outputs[0].html_path.name == "Lois-de-Snell-Descartes-Jules-BERNARD-Daniel-MENGEL-correction.html"


def test_identity_to_review_does_not_influence_output_name(tmp_path):
    from tpstudio.web.workspace import WebWorkspace
    import nbformat
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("Noms : Jules BERNARD et Daniel MENGEL")])
    content = nbformat.writes(notebook).encode()
    with WebWorkspace(tmp_path / "workspace") as workspace:
        copies = workspace.replace_selection((("Paul-DURAND.ipynb", content),))
        from tpstudio.web.identity import identify_selected_copy
        identified = identify_selected_copy(copies[0])
        plan = build_batch_plan_from_web_selection(copies, tmp_path / "out")
    assert identified.identity is not None and identified.identity.status.value == "to_review"
    assert plan.sources[0].output_stem is None
    assert plan.planned_outputs[0].notebook_path.name == "Paul-DURAND-correction.ipynb"
