from hashlib import sha256
from pathlib import Path

import nbformat

from tpstudio.orchestration import (
    BatchCopyDispatchResult, BatchCopyDispatchStatus, BatchDispatchResult,
    NotebookCopySource, analyze_copy,
)
from tpstudio.export import CopyExportOptions, export_analyzed_copy as real_export_analyzed_copy
from tpstudio.projects import known_project_ids
from tpstudio.web.execution import analyze_selected_copy, export_active_copies, run_selected_dispatch
import tpstudio.web.execution as execution
from tpstudio.web.model import SelectedCopy, WebCopyExportState, WebCopyOverride
from tpstudio.web.planning import build_dispatch_requests_from_web_selection
from tpstudio.web.presenters import active_analysis_for_source, batch_dispatch_rows, project_choices_for_source
from tpstudio.projects import torsion_pendulum_teacher_project
from tpstudio.web.state import (
    DISPATCH_RESULT_KEY, DISPATCH_SIGNATURE_KEY, initialize_session_state,
    PROJECT_OVERRIDES_KEY, get_project_overrides, invalidate_if_signature_changed,
    set_dispatch_result, set_project_override,
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


def _empty_copy(tmp_path):
    path = tmp_path / "copy-003.ipynb"
    nbformat.write(nbformat.v4.new_notebook(), path)
    return SelectedCopy("copy-003", path.name, path, sha256(path.read_bytes()).hexdigest())


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


def test_unresolved_project_choices_are_candidates_then_registry(tmp_path):
    empty = _empty_copy(tmp_path)
    result = run_selected_dispatch((empty,))
    assert result.unresolved_count == 1
    assert project_choices_for_source(result, empty.source_id) == known_project_ids()
    row = batch_dispatch_rows(result, (empty,))[0]
    assert row.status == "Aucun TP reconnu"


def test_resolved_not_ready_row_keeps_project_and_never_looks_analyzed(tmp_path):
    path = tmp_path / "pendulum.ipynb"
    nbformat.write(nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell("# Pendule de torsion"),
    ]), path)
    selected = SelectedCopy(
        "copy-004", path.name, path, sha256(path.read_bytes()).hexdigest(),
    )
    dispatch = analyze_copy(
        NotebookCopySource("copy-004", path.name, path),
        project=torsion_pendulum_teacher_project(),
    )
    result = BatchDispatchResult((BatchCopyDispatchResult(
        "copy-004", BatchCopyDispatchStatus.RESOLVED_NOT_READY, dispatch,
    ),))
    row = batch_dispatch_rows(result, (selected,))[0]
    assert row.status == "TP reconnu — analyse indisponible"
    assert row.project_id == "torsion-pendulum"
    assert row.project_title == "Pendule de torsion"
    assert active_analysis_for_source(result, {}, "copy-004") is None


def test_export_active_analyses_skips_resolved_not_ready(tmp_path):
    path = tmp_path / "pendulum.ipynb"
    nbformat.write(nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell("# Pendule de torsion"),
    ]), path)
    dispatch = analyze_copy(
        NotebookCopySource("copy-004", path.name, path),
        project=torsion_pendulum_teacher_project(),
    )
    result = BatchDispatchResult((BatchCopyDispatchResult(
        "copy-004", BatchCopyDispatchStatus.RESOLVED_NOT_READY, dispatch,
    ),))
    assert export_active_copies(
        result, {}, output_dir=tmp_path / "exports", options=CopyExportOptions(),
    ) == {}


def test_active_analysis_override_and_restore(tmp_path):
    copies = _copies(tmp_path)
    result = run_selected_dispatch(copies)
    auto = result.get("copy-002").dispatch.analysis
    explicit = analyze_selected_copy(auto.source, "snells-laws-mvp")
    override = WebCopyOverride("copy-002", "snells-laws-mvp", explicit.analysis)
    assert active_analysis_for_source(result, {}, "copy-002") is auto
    assert active_analysis_for_source(result, {"copy-002": override}, "copy-002") is explicit.analysis
    row = batch_dispatch_rows(result, copies, {"copy-002": override})[1]
    assert row.project_id == "snells-laws-mvp"
    assert row.provenance == "Projet choisi par l'enseignant"
    assert row.confidence is None
    assert row.validated_by_teacher
    assert active_analysis_for_source(result, {}, "copy-002") is auto


def test_overrides_are_cleared_with_new_dispatch_result(tmp_path):
    copies = _copies(tmp_path)
    result = run_selected_dispatch(copies)
    analysis = result.get("copy-002").dispatch.analysis
    override = WebCopyOverride("copy-002", "snells-laws-mvp", analyze_selected_copy(analysis.source, "snells-laws-mvp").analysis)
    state = {}
    initialize_session_state(state)
    set_project_override(state, override)
    assert state[PROJECT_OVERRIDES_KEY]
    set_dispatch_result(state, result, ("new",))
    assert get_project_overrides(state) == {}


def test_export_active_analyses_excludes_unresolved(tmp_path):
    copies = _copies(tmp_path)
    empty = _empty_copy(tmp_path)
    result = run_selected_dispatch(copies + (empty,))
    output = tmp_path / "exports"
    states = export_active_copies(result, {}, output_dir=output, options=CopyExportOptions())
    assert set(states) == {"copy-001", "copy-002"}
    assert all(isinstance(value, WebCopyExportState) and value.result is not None for value in states.values())
    assert all(path.exists() for value in states.values() for path in value.result.output_paths)


def test_export_uses_override_analysis_without_analysis_calls(tmp_path, monkeypatch):
    copies = _copies(tmp_path)
    result = run_selected_dispatch(copies)
    auto = result.get("copy-002").dispatch.analysis
    override = WebCopyOverride("copy-002", "snells-laws-mvp", analyze_selected_copy(auto.source, "snells-laws-mvp").analysis)
    calls = []

    def fake_export(source, analysis, output_dir, **kwargs):
        calls.append((source.source_id, analysis.project_id))
        return real_export_analyzed_copy(source, analysis, output_dir, **kwargs)

    monkeypatch.setattr(execution, "export_analyzed_copy", fake_export)
    states = export_active_copies(
        result, {"copy-002": override}, output_dir=tmp_path / "exports", options=CopyExportOptions(),
    )
    assert calls == [("copy-001", "snells-laws-mvp"), ("copy-002", "snells-laws-mvp")]
    assert states["copy-002"].result.project_id == "snells-laws-mvp"


def test_export_error_isolated_per_copy(tmp_path, monkeypatch):
    copies = _copies(tmp_path)
    result = run_selected_dispatch(copies)
    real = execution.export_analyzed_copy
    calls = []

    def flaky_export(source, analysis, output_dir, **kwargs):
        calls.append(source.source_id)
        if source.source_id == "copy-001":
            raise OSError("destination unavailable")
        return real(source, analysis, output_dir, **kwargs)

    monkeypatch.setattr(execution, "export_analyzed_copy", flaky_export)
    states = export_active_copies(
        result, {}, output_dir=tmp_path / "exports", options=CopyExportOptions(),
    )
    assert calls == ["copy-001", "copy-002"]
    assert states["copy-001"].result is None
    assert states["copy-001"].error_type == "OSError"
    assert states["copy-002"].result is not None
