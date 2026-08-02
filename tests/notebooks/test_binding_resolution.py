from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace

import nbformat
from nbformat.notebooknode import NotebookNode
import pytest

from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    EvaluationBasis,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
)
from tpstudio.notebooks import (
    NotebookBindingResolution,
    NotebookBindingResolutionSet,
    NotebookBindingResolutionStatus,
    NotebookBindingResolver,
    NotebookCellReference,
    resolve_notebook_bindings,
)


def _production(identifier: str, *, depends_on=()) -> ScientificProductionSpec:
    return ScientificProductionSpec(
        identifier, identifier, ScientificProductionKind.QUANTITY,
        (EvaluationBasis.STRUCTURAL,), depends_on=depends_on,
    )


def _plan(*bindings: CellProductionBinding) -> NotebookBindingPlan:
    productions = tuple(
        _production(identifier, depends_on=(("first",) if identifier == "second" else ()))
        for identifier in ("first", "second", "unbound")
    )
    return NotebookBindingPlan(
        "bindings", "Bindings", ScientificProductionPlan("p", "Plan", productions), bindings
    )


def _binding(
    identifier="binding-first",
    production_id="first",
    kind=NotebookCellSelectorKind.CELL_ID,
    value="target",
    scope=None,
) -> CellProductionBinding:
    return CellProductionBinding(
        identifier, production_id, NotebookCellSelector(kind, value),
        scope or CellTextScope.full_source(),
    )


def _cell(source="answer", *, cell_type="markdown", cell_id="target", tags=()):
    constructors = {
        "markdown": nbformat.v4.new_markdown_cell,
        "code": nbformat.v4.new_code_cell,
        "raw": nbformat.v4.new_raw_cell,
    }
    cell = constructors[cell_type](source=source, metadata={"tags": list(tags)})
    if cell_id is None:
        cell.pop("id", None)
    else:
        cell["id"] = cell_id
    return cell


def _notebook(*cells) -> NotebookNode:
    notebook = nbformat.v4.new_notebook()
    notebook.cells = list(cells)
    return notebook


def _resolve(notebook=None, binding=None):
    binding = binding or _binding()
    return resolve_notebook_bindings(notebook or _notebook(_cell()), _plan(binding)).resolutions[0]


def test_status_values_are_exact() -> None:
    assert tuple(item.value for item in NotebookBindingResolutionStatus) == (
        "resolved", "cell_not_found", "cell_ambiguous",
        "text_marker_not_found", "text_marker_ambiguous",
    )


def test_cell_reference_is_immutable_converts_tags_and_preserves_exact_values() -> None:
    reference = NotebookCellReference(2, " markdown ", " Cell-ID ", [" Tag "])  # type: ignore[arg-type]
    assert reference.tags == (" Tag ",)
    assert reference.cell_type == " markdown " and reference.cell_id == " Cell-ID "
    with pytest.raises(FrozenInstanceError):
        reference.index = 1  # type: ignore[misc]


@pytest.mark.parametrize("index", [-1, True, 1.5])
def test_cell_reference_rejects_invalid_index(index) -> None:
    with pytest.raises((TypeError, ValueError)):
        NotebookCellReference(index, "markdown", None, ())


@pytest.mark.parametrize("cell_type", ["", "  ", 1])
def test_cell_reference_rejects_invalid_cell_type(cell_type) -> None:
    with pytest.raises((TypeError, ValueError)):
        NotebookCellReference(0, cell_type, None, ())


def test_cell_reference_rejects_invalid_id_and_tags() -> None:
    with pytest.raises(TypeError):
        NotebookCellReference(0, "markdown", 1, ())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        NotebookCellReference(0, "markdown", None, ("ok", 1))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        NotebookCellReference(0, "markdown", None, "tag")  # type: ignore[arg-type]


def test_resolution_is_immutable_and_exposes_derived_properties() -> None:
    result = _resolve()
    assert result.binding_id == "binding-first" and result.production_id == "first"
    assert result.selector is result.binding.selector
    assert result.text_scope is result.binding.text_scope
    assert result.resolved and not result.failed
    with pytest.raises(FrozenInstanceError):
        result.text = "changed"  # type: ignore[misc]


def test_resolved_invariants_reject_incoherent_objects() -> None:
    binding = _binding()
    cell = NotebookCellReference(0, "markdown", "target", ())
    valid = NotebookBindingResolution(
        binding, NotebookBindingResolutionStatus.RESOLVED, (0,), cell, "abc", 1, 4
    )
    for changes in (
        {"candidate_indices": ()}, {"cell": None},
        {"cell": NotebookCellReference(1, "markdown", "target", ())},
        {"text": None}, {"text_start": None}, {"text_end": None},
        {"text_start": 5}, {"text": "ab"},
    ):
        with pytest.raises((TypeError, ValueError)):
            replace(valid, **changes)


@pytest.mark.parametrize(
    ("status", "indices", "cell"),
    [
        (NotebookBindingResolutionStatus.CELL_NOT_FOUND, (), None),
        (NotebookBindingResolutionStatus.CELL_AMBIGUOUS, (0, 2), None),
        (NotebookBindingResolutionStatus.TEXT_MARKER_NOT_FOUND, (1,), NotebookCellReference(1, "markdown", None, ())),
        (NotebookBindingResolutionStatus.TEXT_MARKER_AMBIGUOUS, (1,), NotebookCellReference(1, "markdown", None, ())),
    ],
)
def test_each_failure_status_has_valid_shape(status, indices, cell) -> None:
    result = NotebookBindingResolution(_binding(), status, indices, cell)
    assert result.failed and not result.resolved and result.text is None


def test_failure_statuses_reject_text_and_wrong_cardinality() -> None:
    binding = _binding()
    with pytest.raises(ValueError):
        NotebookBindingResolution(binding, NotebookBindingResolutionStatus.CELL_NOT_FOUND, (0,))
    with pytest.raises(ValueError):
        NotebookBindingResolution(binding, NotebookBindingResolutionStatus.CELL_AMBIGUOUS, (0,))
    with pytest.raises(ValueError):
        NotebookBindingResolution(binding, NotebookBindingResolutionStatus.TEXT_MARKER_NOT_FOUND, ())
    with pytest.raises(ValueError):
        NotebookBindingResolution(binding, NotebookBindingResolutionStatus.CELL_NOT_FOUND, text="")


def test_candidate_indices_convert_and_must_be_strictly_increasing_ints() -> None:
    result = NotebookBindingResolution(
        _binding(), NotebookBindingResolutionStatus.CELL_AMBIGUOUS, [0, 2]  # type: ignore[arg-type]
    )
    assert result.candidate_indices == (0, 2)
    for indices in ((1, 1), (2, 1), (0, True), (-1, 2)):
        with pytest.raises((TypeError, ValueError)):
            replace(result, candidate_indices=indices)


def test_resolution_set_is_immutable_ordered_and_has_complete_api() -> None:
    second = _binding("b-second", "second", value="missing")
    first = _binding("b-first", "first")
    plan = _plan(second, first)
    results = resolve_notebook_bindings(_notebook(_cell()), plan)
    assert tuple(item.binding_id for item in results) == ("b-first", "b-second")
    assert len(results) == 2
    assert results.get("b-first") is results.resolutions[0]
    assert results.get("unknown") is None
    assert results.for_production("first") == (results.resolutions[0],)
    assert results.for_production("unbound") == ()
    with pytest.raises(ValueError):
        results.for_production("unknown")
    assert results.for_status(NotebookBindingResolutionStatus.RESOLVED) == results.resolved
    assert results.failures == (results.resolutions[1],)
    assert results.has_failures and not results.all_resolved
    with pytest.raises(FrozenInstanceError):
        results.resolutions = ()  # type: ignore[misc]


def test_resolution_set_rejects_missing_foreign_duplicate_and_wrong_order() -> None:
    first = _binding("first-binding", "first")
    second = _binding("second-binding", "second", value="other")
    plan = _plan(second, first)
    first_result = _resolve(binding=first)
    second_result = _resolve(binding=second)
    with pytest.raises(ValueError):
        NotebookBindingResolutionSet(plan, (first_result,))
    with pytest.raises(ValueError):
        NotebookBindingResolutionSet(plan, (second_result, first_result))
    foreign = _binding("first-binding", "first")
    with pytest.raises(ValueError):
        NotebookBindingResolutionSet(plan, (_resolve(binding=foreign), second_result))
    with pytest.raises(TypeError):
        NotebookBindingResolutionSet(plan, (object(), object()))  # type: ignore[arg-type]


@pytest.mark.parametrize("cell_type", ["markdown", "code", "raw"])
def test_cell_id_resolves_all_standard_cell_types_with_exact_full_source(cell_type) -> None:
    source = "  answer\n"
    result = _resolve(_notebook(_cell(source, cell_type=cell_type)))
    assert result.status is NotebookBindingResolutionStatus.RESOLVED
    assert result.text == source and result.text_start == 0 and result.text_end == len(source)
    assert result.cell is not None and result.cell.cell_type == cell_type


def test_empty_source_is_successfully_resolved() -> None:
    result = _resolve(_notebook(_cell("")))
    assert result.resolved and result.text == "" and result.text_start == result.text_end == 0


@pytest.mark.parametrize(
    ("kind", "value", "cell"),
    [
        (NotebookCellSelectorKind.CELL_ID, "target", _cell(cell_id="target")),
        (NotebookCellSelectorKind.TAG, "answer", _cell(cell_id=None, tags=("answer",))),
        (NotebookCellSelectorKind.SOURCE_MARKER, "TPSTUDIO: answer", _cell("x TPSTUDIO: answer x", cell_id=None)),
    ],
)
def test_three_selectors_resolve_literally(kind, value, cell) -> None:
    result = _resolve(_notebook(cell), _binding(kind=kind, value=value))
    assert result.resolved and result.candidate_indices == (0,)


@pytest.mark.parametrize(
    ("kind", "value", "cell"),
    [
        (NotebookCellSelectorKind.CELL_ID, "Target", _cell(cell_id="target")),
        (NotebookCellSelectorKind.TAG, "Answer", _cell(tags=("answer",))),
        (NotebookCellSelectorKind.SOURCE_MARKER, "Answer", _cell("answer")),
        (NotebookCellSelectorKind.SOURCE_MARKER, ".*", _cell("ordinary text")),
    ],
)
def test_selectors_are_case_sensitive_and_source_marker_is_not_regex(kind, value, cell) -> None:
    result = _resolve(_notebook(cell), _binding(kind=kind, value=value))
    assert result.status is NotebookBindingResolutionStatus.CELL_NOT_FOUND


@pytest.mark.parametrize("kind", list(NotebookCellSelectorKind))
def test_not_found_is_structured_for_each_selector(kind) -> None:
    result = _resolve(_notebook(_cell(cell_id=None)), _binding(kind=kind, value="absent"))
    assert result.status is NotebookBindingResolutionStatus.CELL_NOT_FOUND
    assert result.candidate_indices == () and result.cell is None


@pytest.mark.parametrize("kind", list(NotebookCellSelectorKind))
def test_ambiguity_is_structured_for_each_selector_and_indices_follow_notebook(kind) -> None:
    if kind is NotebookCellSelectorKind.CELL_ID:
        cells = (_cell(cell_id="same"), _cell(cell_id="other"), _cell(cell_id="same"))
    elif kind is NotebookCellSelectorKind.TAG:
        cells = (_cell(tags=("same",)), _cell(), _cell(tags=("same",)))
    else:
        cells = (_cell("same"), _cell("other"), _cell("same"))
    result = _resolve(_notebook(*cells), _binding(kind=kind, value="same"))
    assert result.status is NotebookBindingResolutionStatus.CELL_AMBIGUOUS
    assert result.candidate_indices == (0, 2) and result.cell is None


def test_repeated_source_selector_inside_one_cell_is_not_cell_ambiguity() -> None:
    result = _resolve(
        _notebook(_cell("MARK MARK", cell_id=None)),
        _binding(kind=NotebookCellSelectorKind.SOURCE_MARKER, value="MARK"),
    )
    assert result.resolved and result.candidate_indices == (0,)


def test_after_marker_preserves_exact_whitespace_and_bounds() -> None:
    source = "Déterminer g.\nRéponse :\n  g = 9,7  \n"
    marker = "Réponse :"
    result = _resolve(
        _notebook(_cell(source)), _binding(scope=CellTextScope.after_marker(marker))
    )
    start = source.index(marker) + len(marker)
    assert result.text == "\n  g = 9,7  \n"
    assert result.text_start == start and result.text_end == len(source)
    assert result.text == source[result.text_start:result.text_end]


def test_after_marker_allows_empty_fragment() -> None:
    result = _resolve(
        _notebook(_cell("Réponse :")),
        _binding(scope=CellTextScope.after_marker("Réponse :")),
    )
    assert result.resolved and result.text == ""


def test_scope_marker_absence_and_ambiguity_are_structured() -> None:
    missing = _resolve(
        _notebook(_cell("answer")),
        _binding(scope=CellTextScope.after_marker("Réponse :")),
    )
    ambiguous = _resolve(
        _notebook(_cell("M answer M")),
        _binding(scope=CellTextScope.after_marker("M")),
    )
    assert missing.status is NotebookBindingResolutionStatus.TEXT_MARKER_NOT_FOUND
    assert ambiguous.status is NotebookBindingResolutionStatus.TEXT_MARKER_AMBIGUOUS
    assert missing.cell is not None and ambiguous.cell is not None


def test_overlapping_scope_marker_occurrences_are_ambiguous() -> None:
    result = _resolve(
        _notebook(_cell("ababa")),
        _binding(scope=CellTextScope.after_marker("aba")),
    )
    assert result.status is NotebookBindingResolutionStatus.TEXT_MARKER_AMBIGUOUS
    assert result.candidate_indices == (0,)
    assert result.cell is not None and result.cell.index == 0
    assert result.text is None
    assert result.text_start is None
    assert result.text_end is None


def test_scope_marker_is_independent_from_source_selector() -> None:
    binding = _binding(
        kind=NotebookCellSelectorKind.SOURCE_MARKER,
        value="TPSTUDIO: first",
        scope=CellTextScope.after_marker("Réponse :"),
    )
    result = _resolve(_notebook(_cell("TPSTUDIO: first\nRéponse :\nanswer")), binding)
    assert result.resolved and result.text == "\nanswer"


def test_same_cell_for_multiple_bindings_and_multiple_bindings_per_production_are_not_aggregated() -> None:
    shared = NotebookCellSelectorKind.TAG
    bindings = (
        _binding("first-a", "first", shared, "shared"),
        _binding("first-b", "first", shared, "shared", CellTextScope.after_marker("M:")),
        _binding("second", "second", shared, "shared"),
    )
    results = resolve_notebook_bindings(_notebook(_cell("M:value", tags=("shared",))), _plan(*bindings))
    assert len(results.for_production("first")) == 2
    assert all(item.cell.index == 0 for item in results if item.cell is not None)
    assert tuple(item.text for item in results) == ("M:value", "value", "M:value")
    assert not hasattr(results, "combined_text") and not hasattr(results, "first_text")


def test_resolver_rejects_invalid_arguments() -> None:
    with pytest.raises(TypeError):
        resolve_notebook_bindings("file.ipynb", _plan(_binding()))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        resolve_notebook_bindings(_notebook(), object())  # type: ignore[arg-type]


def test_malformed_notebook_and_cells_are_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_notebook_bindings(NotebookNode(), _plan(_binding()))
    for field_name, value in (
        ("cell_type", ""), ("cell_type", 1), ("source", ["x"]),
        ("id", 1), ("metadata", None),
    ):
        cell = _cell()
        cell[field_name] = value
        with pytest.raises((TypeError, ValueError)):
            resolve_notebook_bindings(_notebook(cell), _plan(_binding()))
    for tags in ("tag", ["ok", 1]):
        cell = _cell()
        cell.metadata.tags = tags
        with pytest.raises(TypeError):
            resolve_notebook_bindings(_notebook(cell), _plan(_binding()))


def test_plain_mapping_cell_is_rejected_without_correction() -> None:
    notebook = _notebook()
    notebook.cells = [{"cell_type": "markdown", "source": "answer", "metadata": {}}]
    with pytest.raises(TypeError):
        resolve_notebook_bindings(notebook, _plan(_binding()))


def test_resolution_does_not_mutate_notebook_cells_or_inspect_outputs() -> None:
    cell = _cell("print('never executed')", cell_type="code")
    cell.outputs = [NotebookNode({"ignored": "untouched"})]
    notebook = _notebook(cell)
    before = deepcopy(notebook)
    result = _resolve(notebook)
    assert result.text == "print('never executed')"
    assert notebook == before


def test_two_calls_are_equal_and_cell_reference_stores_no_source_or_runtime_data() -> None:
    notebook = _notebook(_cell("answer"))
    plan = _plan(_binding())
    assert resolve_notebook_bindings(notebook, plan) == resolve_notebook_bindings(notebook, plan)
    names = {field.name for field in fields(NotebookCellReference)}
    assert names == {"index", "cell_type", "cell_id", "tags"}
    assert not names & {"source", "outputs", "execution_count", "metadata", "path"}


def test_convenience_function_only_delegates(monkeypatch) -> None:
    sentinel = object()
    calls = []
    def fake_resolve(self, notebook, plan):
        calls.append((notebook, plan))
        return sentinel
    monkeypatch.setattr(NotebookBindingResolver, "resolve", fake_resolve)
    notebook = _notebook()
    plan = _plan(_binding())
    assert resolve_notebook_bindings(notebook, plan) is sentinel
    assert calls == [(notebook, plan)]
