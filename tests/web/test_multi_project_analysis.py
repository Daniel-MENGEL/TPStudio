from hashlib import sha256
from pathlib import Path

import nbformat

from tpstudio.orchestration import BatchDispatchResult
from tpstudio.web.execution import run_selected_dispatch
import tpstudio.web.execution as execution
from tpstudio.web.model import SelectedCopy
from tpstudio.web.planning import build_dispatch_requests_from_web_selection
from tpstudio.web.presenters import batch_dispatch_rows
from tpstudio.web.state import (
    DISPATCH_RESULT_KEY, DISPATCH_SIGNATURE_KEY, initialize_session_state,
    invalidate_if_signature_changed, set_dispatch_result,
)


def _copies(tmp_path):
    texts = (
        "# Lois de Snell-Descartes\nÉtudier la réfraction : sin(i1) et sin(i2).",
        "# Formation d'une image par une lentille mince\nRelation de conjugaison : 1/OA' - 1/OA = 1/f'.",
    )
    copies = []
    for index, text in enumerate(texts, 1):
        path = tmp_path / f"copy-{index:03}.ipynb"
        nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell(text)]), path)
        copies.append(SelectedCopy(
            f"copy-{index:03}", path.name, path, sha256(path.read_bytes()).hexdigest(),
        ))
    return tuple(copies)


def test_web_selection_becomes_project_agnostic_requests(tmp_path):
    copies = _copies(tmp_path)
    requests = build_dispatch_requests_from_web_selection(copies)
    assert [request.source_id for request in requests] == ["copy-001", "copy-002"]
    assert all(request.project is None for request in requests)
    assert all(request.source.source_id == request.source_id for request in requests)


def test_web_analysis_dispatches_snell_and_lens_per_copy(tmp_path):
    copies = _copies(tmp_path)
    result = run_selected_dispatch(copies)
    assert isinstance(result, BatchDispatchResult)
    assert result.analyzed_count == 2
    assert [item.dispatch.analysis.project_id for item in result.copies] == [
        "snells-laws-mvp", "thin-lens-image",
    ]
    rows = batch_dispatch_rows(result, copies)
    assert [row.project_title for row in rows] == [
        "Lois de Snell-Descartes", "Formation d'une image par une lentille mince",
    ]
    assert [row.provenance for row in rows] == ["Détection automatique", "Détection automatique"]
    assert [row.confidence for row in rows] == ["Haute", "Haute"]
    assert rows[0].evidence
    assert all(isinstance(kind, str) and isinstance(text, str) for kind, text in rows[0].evidence)


def test_dispatch_result_state_is_invalidated_on_signature_change():
    state = {}
    initialize_session_state(state)
    result = BatchDispatchResult(())
    set_dispatch_result(state, result, ("old",))
    assert state[DISPATCH_RESULT_KEY] is result
    assert state[DISPATCH_SIGNATURE_KEY] == ("old",)
    assert invalidate_if_signature_changed(state, ("new",))
    assert state[DISPATCH_RESULT_KEY] is None
    assert state[DISPATCH_SIGNATURE_KEY] is None


def test_web_execution_calls_generic_run_batch_once(tmp_path, monkeypatch):
    copies = _copies(tmp_path)
    observed = {}
    expected = BatchDispatchResult(())

    def fake_run_batch(requests, *, options=None, continue_on_error=True):
        observed["requests"] = tuple(requests)
        observed["options"] = options
        observed["continue_on_error"] = continue_on_error
        return expected

    monkeypatch.setattr(execution, "run_batch", fake_run_batch)
    assert run_selected_dispatch(copies) is expected
    assert [request.source_id for request in observed["requests"]] == ["copy-001", "copy-002"]
    assert observed["options"] is None
    assert observed["continue_on_error"] is True
