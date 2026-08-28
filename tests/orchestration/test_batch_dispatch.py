from dataclasses import replace
from pathlib import Path

import nbformat
import pytest

import tpstudio.orchestration.batch_dispatch as batch_dispatch
from tpstudio.orchestration import (
    BatchCopyDispatchResult,
    BatchCopyDispatchStatus,
    BatchCopyRequest,
    BatchDispatchResult,
    CopyAnalysisOptions,
    NotebookCopySource,
    ProjectSelectionProvenance,
    analyze_copy,
    run_batch,
)
from tpstudio.projects import snells_laws_teacher_project
from tpstudio.projects.first_order_transient import first_order_transient_teacher_project
from tpstudio.web.presenters import exportable_count

from tests.orchestration.test_copy_analysis import _first_order_notebook, _notebook, _RecordingSemanticProvider


def _source(tmp_path: Path, notebook, name: str) -> NotebookCopySource:
    path = tmp_path / name
    nbformat.write(notebook, path)
    return NotebookCopySource(name, name, path)


def _snell_notebook():
    notebook = _notebook()
    notebook.cells.insert(0, nbformat.v4.new_markdown_cell("# Lois de Snell-Descartes"))
    return notebook


def _lens_notebook():
    return nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(
            "# Formation d'une image par une lentille mince\n"
            "Relation de conjugaison : 1/OA' - 1/OA = 1/f'."
        )
    ])


def _ambiguous_notebook():
    return nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(
            "# Lois de Snell-Descartes\nÉtudier la réfraction et l'indice.\n"
            "# Formation d'une image par une lentille mince\n"
            "Relation de conjugaison : 1/OA' - 1/OA = 1/f'."
        )
    ])


def test_auto_snell_and_lens_are_analyzed_in_input_order(tmp_path: Path) -> None:
    result = run_batch((
        BatchCopyRequest("snell", _source(tmp_path, _snell_notebook(), "snell.ipynb")),
        BatchCopyRequest("lens", _source(tmp_path, _lens_notebook(), "lens.ipynb")),
    ))
    assert [item.source_id for item in result.copies] == ["snell", "lens"]
    assert [item.dispatch.resolution.selected_project_id for item in result.copies] == [
        "snells-laws-mvp", "thin-lens-image",
    ]
    assert all(item.status is BatchCopyDispatchStatus.ANALYZED for item in result.copies)
    assert result.analyzed_count == 2
    assert result.unresolved_count == result.error_count == 0
    assert result.project_ids == ("snells-laws-mvp", "thin-lens-image")


def test_unresolved_empty_is_non_fatal_between_two_analyses(tmp_path: Path) -> None:
    result = run_batch((
        BatchCopyRequest("snell", _source(tmp_path, _snell_notebook(), "snell.ipynb")),
        BatchCopyRequest("empty", _source(tmp_path, nbformat.v4.new_notebook(), "empty.ipynb")),
        BatchCopyRequest("lens", _source(tmp_path, _lens_notebook(), "lens.ipynb")),
    ), continue_on_error=False)
    assert [item.status for item in result.copies] == [
        BatchCopyDispatchStatus.ANALYZED,
        BatchCopyDispatchStatus.UNRESOLVED,
        BatchCopyDispatchStatus.ANALYZED,
    ]
    assert result.analyzed_count == 2 and result.unresolved_count == 1 and result.error_count == 0
    assert result.copies[1].dispatch.resolution.candidates == ()


def test_medium_and_high_high_are_unresolved_and_other_copies_continue(tmp_path: Path) -> None:
    medium = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell("Tracer sin(i1) en fonction de sin(i2).")
    ])
    result = run_batch((
        BatchCopyRequest("medium", _source(tmp_path, medium, "medium.ipynb")),
        BatchCopyRequest("ambiguous", _source(tmp_path, _ambiguous_notebook(), "ambiguous.ipynb")),
        BatchCopyRequest("snell", _source(tmp_path, _snell_notebook(), "snell.ipynb")),
    ))
    assert [item.status for item in result.copies] == [
        BatchCopyDispatchStatus.UNRESOLVED,
        BatchCopyDispatchStatus.UNRESOLVED,
        BatchCopyDispatchStatus.ANALYZED,
    ]
    assert result.copies[0].dispatch.resolution.requires_teacher_choice is True
    assert len(result.copies[1].dispatch.resolution.candidates) == 2
    assert result.analyzed_count == 1 and result.unresolved_count == 2


def test_technical_error_isolated_when_continuing(tmp_path: Path, monkeypatch) -> None:
    original = batch_dispatch.analyze_copy
    calls = []

    def failing_once(source, *, project=None, options=None):
        calls.append(source.path.stem)
        if source.path.stem == "bad":
            raise ValueError("controlled failure")
        return original(source, project=project, options=options)

    monkeypatch.setattr(batch_dispatch, "analyze_copy", failing_once)
    result = run_batch((
        BatchCopyRequest("good", _source(tmp_path, _snell_notebook(), "good.ipynb")),
        BatchCopyRequest("bad", _source(tmp_path, _snell_notebook(), "bad.ipynb")),
        BatchCopyRequest("last", _source(tmp_path, _lens_notebook(), "last.ipynb")),
    ))
    assert calls == ["good", "bad", "last"]
    assert [item.status for item in result.copies] == [
        BatchCopyDispatchStatus.ANALYZED,
        BatchCopyDispatchStatus.ERROR,
        BatchCopyDispatchStatus.ANALYZED,
    ]
    assert result.copies[1].error_type == "ValueError"
    assert result.error_count == 1


def test_technical_error_skips_following_copies_when_requested(tmp_path: Path, monkeypatch) -> None:
    def failing(source, *, project=None, options=None):
        if source.path.stem == "bad":
            raise RuntimeError("controlled failure")
        return analyze_copy(source, project=project, options=options)

    monkeypatch.setattr(batch_dispatch, "analyze_copy", failing)
    result = run_batch((
        BatchCopyRequest("bad", _source(tmp_path, _snell_notebook(), "bad.ipynb")),
        BatchCopyRequest("last", _source(tmp_path, _lens_notebook(), "last.ipynb")),
    ), continue_on_error=False)
    assert [item.status for item in result.copies] == [
        BatchCopyDispatchStatus.ERROR,
        BatchCopyDispatchStatus.SKIPPED,
    ]
    assert result.copies[1].error_message
    assert result.skipped_count == 1


def test_keyboard_interrupt_is_not_absorbed(tmp_path: Path, monkeypatch) -> None:
    def interrupt(source, *, project=None, options=None):
        raise KeyboardInterrupt()

    monkeypatch.setattr(batch_dispatch, "analyze_copy", interrupt)
    request = BatchCopyRequest("copy", _source(tmp_path, _snell_notebook(), "copy.ipynb"))
    with pytest.raises(KeyboardInterrupt):
        run_batch((request,))


def test_options_same_object_is_forwarded_to_every_copy(tmp_path: Path, monkeypatch) -> None:
    base_source = _source(tmp_path, _snell_notebook(), "base.ipynb")
    base_dispatch = analyze_copy(base_source, project=snells_laws_teacher_project())
    options = CopyAnalysisOptions(build_diagnostics=False, render_feedback=False)
    captured = []

    def fake_analyze(source, *, project=None, options=None):
        captured.append(options)
        project = project or snells_laws_teacher_project()
        analysis = replace(base_dispatch.analysis, source=source, project=project, options=options)
        return replace(base_dispatch, analysis=analysis)

    monkeypatch.setattr(batch_dispatch, "analyze_copy", fake_analyze)
    result = run_batch((
        BatchCopyRequest("one", _source(tmp_path, _snell_notebook(), "one.ipynb")),
        BatchCopyRequest("two", _source(tmp_path, _snell_notebook(), "two.ipynb")),
    ), options=options)
    assert captured == [options, options]
    assert all(item.status is BatchCopyDispatchStatus.ANALYZED for item in result.copies)


def test_semantic_provider_same_instance_is_forwarded_in_request_order(tmp_path: Path, monkeypatch) -> None:
    first = _source(tmp_path, _snell_notebook(), "first.ipynb")
    second = _source(tmp_path, _snell_notebook(), "second.ipynb")
    base = analyze_copy(first, project=snells_laws_teacher_project())
    provider = object()
    calls = []

    def fake_analyze(source, *, project=None, options=None, semantic_provider=None):
        calls.append((source.path.stem, semantic_provider))
        return base

    monkeypatch.setattr(batch_dispatch, "analyze_copy", fake_analyze)
    result = run_batch(
        (BatchCopyRequest("first", first), BatchCopyRequest("second", second)),
        semantic_provider=provider,
    )
    assert calls == [("first", provider), ("second", provider)]
    assert result.analyzed_count == 2


def test_semantic_provider_is_limited_to_selected_source_ids(tmp_path: Path, monkeypatch) -> None:
    first = _source(tmp_path, _snell_notebook(), "first.ipynb")
    reference = _source(tmp_path, _snell_notebook(), "reference.ipynb")
    base = analyze_copy(first, project=snells_laws_teacher_project())
    provider = object()
    calls = []

    def fake_analyze(source, *, project=None, options=None, semantic_provider=None):
        calls.append((source.path.stem, semantic_provider))
        return base

    monkeypatch.setattr(batch_dispatch, "analyze_copy", fake_analyze)
    result = run_batch(
        (
            BatchCopyRequest("first", first),
            BatchCopyRequest("reference", reference),
        ),
        semantic_provider=provider,
        semantic_source_ids=frozenset({"first"}),
    )
    assert calls == [("first", provider), ("reference", None)]
    assert result.analyzed_count == 2


def test_progress_callback_reports_every_copy_in_order(tmp_path: Path, monkeypatch) -> None:
    first = _source(tmp_path, _snell_notebook(), "first.ipynb")
    second = _source(tmp_path, _snell_notebook(), "second.ipynb")
    base = analyze_copy(first, project=snells_laws_teacher_project())
    events = []

    monkeypatch.setattr(batch_dispatch, "analyze_copy", lambda *args, **kwargs: base)
    run_batch(
        (BatchCopyRequest("first", first), BatchCopyRequest("second", second)),
        progress_callback=lambda completed, total, source_id: events.append(
            (completed, total, source_id)
        ),
    )
    assert events == [(1, 2, "first"), (2, 2, "second")]


def test_semantic_provider_is_not_forwarded_to_skipped_requests(tmp_path: Path, monkeypatch) -> None:
    provider = object()
    calls = []

    def failing(source, *, project=None, options=None, semantic_provider=None):
        calls.append((source.path.stem, semantic_provider))
        raise RuntimeError("controlled failure")

    monkeypatch.setattr(batch_dispatch, "analyze_copy", failing)
    result = run_batch(
        (
            BatchCopyRequest("bad", _source(tmp_path, _snell_notebook(), "bad.ipynb")),
            BatchCopyRequest("last", _source(tmp_path, _lens_notebook(), "last.ipynb")),
        ),
        continue_on_error=False,
        semantic_provider=provider,
    )
    assert calls == [("bad", provider)]
    assert [item.status for item in result.copies] == [
        BatchCopyDispatchStatus.ERROR, BatchCopyDispatchStatus.SKIPPED,
    ]


def test_run_batch_keeps_not_ready_status_with_semantic_preview(tmp_path: Path) -> None:
    notebook = _first_order_notebook()
    source = _source(tmp_path, notebook, "first-order.ipynb")
    before = source.path.read_bytes()
    provider = _RecordingSemanticProvider()
    result = run_batch(
        (BatchCopyRequest(
            "first-order", source, first_order_transient_teacher_project()
        ),),
        semantic_provider=provider,
    )
    item = result.copies[0]
    assert item.status is BatchCopyDispatchStatus.RESOLVED_NOT_READY
    assert item.dispatch is not None
    assert item.dispatch.analysis is None
    assert [analysis.contract.production_id for analysis in item.dispatch.semantic_response_analyses] == [
        "charge_objective", "energy_objective", "leakage_protocol",
    ]
    assert len(provider.calls) == 3
    assert source.path.read_bytes() == before
    assert exportable_count(result, {}) == 0


def test_explicit_and_auto_projects_coexist_per_copy(tmp_path: Path) -> None:
    result = run_batch((
        BatchCopyRequest("forced-snell", _source(tmp_path, _lens_notebook(), "forced.ipynb"), snells_laws_teacher_project()),
        BatchCopyRequest("auto-lens", _source(tmp_path, _lens_notebook(), "auto.ipynb")),
    ))
    assert result.copies[0].dispatch.provenance is ProjectSelectionProvenance.EXPLICIT
    assert result.copies[0].dispatch.analysis.project_id == "snells-laws-mvp"
    assert result.copies[1].dispatch.provenance is ProjectSelectionProvenance.AUTO_RESOLVED
    assert result.copies[1].dispatch.analysis.project_id == "thin-lens-image"


def test_two_copies_same_project_are_independent(tmp_path: Path) -> None:
    result = run_batch((
        BatchCopyRequest("one", _source(tmp_path, _snell_notebook(), "one.ipynb")),
        BatchCopyRequest("two", _source(tmp_path, _snell_notebook(), "two.ipynb")),
    ))
    assert result.analyzed_count == 2
    assert result.project_ids == ("snells-laws-mvp",)
    assert result.copies[0].dispatch.analysis is not result.copies[1].dispatch.analysis


def test_status_invariants_and_no_global_project_id() -> None:
    assert not hasattr(BatchDispatchResult, "project_id")
    with pytest.raises(ValueError):
        BatchCopyDispatchResult("x", BatchCopyDispatchStatus.ANALYZED)
    with pytest.raises(ValueError):
        BatchCopyDispatchResult("x", BatchCopyDispatchStatus.ERROR)


def test_one_batch_can_contain_all_four_statuses_and_project_ids_are_filtered(tmp_path: Path, monkeypatch) -> None:
    analyzed_source = _source(tmp_path, _snell_notebook(), "analyzed.ipynb")
    unresolved_source = _source(tmp_path, nbformat.v4.new_notebook(), "unresolved.ipynb")
    error_source = _source(tmp_path, _snell_notebook(), "error.ipynb")
    skipped_source = _source(tmp_path, _lens_notebook(), "skipped.ipynb")
    analyzed_dispatch = analyze_copy(analyzed_source, project=snells_laws_teacher_project())
    unresolved_dispatch = analyze_copy(unresolved_source)

    def controlled(source, *, project=None, options=None):
        if source.path.stem == "error":
            raise RuntimeError("controlled batch error")
        return analyzed_dispatch if source.path.stem == "analyzed" else unresolved_dispatch

    monkeypatch.setattr(batch_dispatch, "analyze_copy", controlled)
    result = run_batch((
        BatchCopyRequest("analyzed", analyzed_source),
        BatchCopyRequest("unresolved", unresolved_source),
        BatchCopyRequest("error", error_source),
        BatchCopyRequest("skipped", skipped_source),
    ), continue_on_error=False)
    assert [item.status for item in result.copies] == [
        BatchCopyDispatchStatus.ANALYZED,
        BatchCopyDispatchStatus.UNRESOLVED,
        BatchCopyDispatchStatus.ERROR,
        BatchCopyDispatchStatus.SKIPPED,
    ]
    assert (result.analyzed_count, result.unresolved_count, result.error_count, result.skipped_count) == (1, 1, 1, 1)
    assert result.project_ids == ("snells-laws-mvp",)


def test_project_ids_are_unique_first_seen_and_exclude_non_analyzed(tmp_path: Path, monkeypatch) -> None:
    first = _source(tmp_path, _snell_notebook(), "first.ipynb")
    second = _source(tmp_path, _lens_notebook(), "second.ipynb")
    unresolved = _source(tmp_path, nbformat.v4.new_notebook(), "unresolved.ipynb")
    first_dispatch = analyze_copy(first, project=snells_laws_teacher_project())
    second_dispatch = analyze_copy(second, project=snells_laws_teacher_project())
    unresolved_dispatch = analyze_copy(unresolved)

    def controlled(source, *, project=None, options=None):
        if source.path.stem == "unresolved":
            return unresolved_dispatch
        return first_dispatch if source.path.stem == "first" else second_dispatch

    monkeypatch.setattr(batch_dispatch, "analyze_copy", controlled)
    result = run_batch((
        BatchCopyRequest("first", first),
        BatchCopyRequest("second", second),
        BatchCopyRequest("unresolved", unresolved),
    ))
    assert result.project_ids == ("snells-laws-mvp",)


def test_skipped_requests_never_call_analyze_copy(tmp_path: Path, monkeypatch) -> None:
    calls = []
    original = batch_dispatch.analyze_copy

    def controlled(source, *, project=None, options=None):
        calls.append(source.path.stem)
        if source.path.stem == "error":
            raise RuntimeError("controlled batch error")
        return original(source, project=project, options=options)

    monkeypatch.setattr(batch_dispatch, "analyze_copy", controlled)
    result = run_batch((
        BatchCopyRequest("first", _source(tmp_path, _snell_notebook(), "first.ipynb")),
        BatchCopyRequest("error", _source(tmp_path, _snell_notebook(), "error.ipynb")),
        BatchCopyRequest("third", _source(tmp_path, _lens_notebook(), "third.ipynb")),
        BatchCopyRequest("fourth", _source(tmp_path, _snell_notebook(), "fourth.ipynb")),
    ), continue_on_error=False)
    assert calls == ["first", "error"]
    assert [item.status for item in result.copies] == [
        BatchCopyDispatchStatus.ANALYZED,
        BatchCopyDispatchStatus.ERROR,
        BatchCopyDispatchStatus.SKIPPED,
        BatchCopyDispatchStatus.SKIPPED,
    ]
