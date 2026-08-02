from dataclasses import FrozenInstanceError, fields

import pytest

from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    CellTextScopeKind,
    EvaluationBasis,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
)


def _production(
    identifier: str,
    kind: ScientificProductionKind = ScientificProductionKind.QUANTITY,
    *,
    depends_on: tuple[str, ...] = (),
) -> ScientificProductionSpec:
    return ScientificProductionSpec(
        identifier,
        f"Production {identifier}",
        kind,
        (EvaluationBasis.STRUCTURAL,),
        depends_on=depends_on,
    )


def _pendulum_plan() -> ScientificProductionPlan:
    return ScientificProductionPlan(
        "pendulum",
        "Pendule",
        (
            _production("period_plot", ScientificProductionKind.PLOT),
            _production("gravity_dynamic", depends_on=("period_plot",)),
            _production("gravity_static"),
            _production(
                "gravity_comparison",
                ScientificProductionKind.COMPARISON,
                depends_on=("gravity_dynamic", "gravity_static"),
            ),
            _production(
                "uncertainty_justification",
                ScientificProductionKind.JUSTIFICATION,
                depends_on=("gravity_dynamic",),
            ),
            _production(
                "final_interpretation",
                ScientificProductionKind.INTERPRETATION,
                depends_on=("gravity_comparison",),
            ),
        ),
    )


def _selector(
    value: str = "answer-gravity-dynamic",
    kind: NotebookCellSelectorKind = NotebookCellSelectorKind.TAG,
) -> NotebookCellSelector:
    return NotebookCellSelector(kind, value)


def _binding(
    identifier: str,
    production_id: str,
    selector: NotebookCellSelector | None = None,
    scope: CellTextScope | None = None,
) -> CellProductionBinding:
    return CellProductionBinding(
        identifier,
        production_id,
        selector or _selector(),
        scope or CellTextScope.full_source(),
    )


def test_enum_values_are_stable() -> None:
    assert tuple(item.value for item in NotebookCellSelectorKind) == (
        "cell_id", "tag", "source_marker"
    )
    assert tuple(item.value for item in CellTextScopeKind) == (
        "full_source", "after_marker"
    )


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        (NotebookCellSelectorKind.CELL_ID, "cell-gravity-dynamic"),
        (NotebookCellSelectorKind.TAG, "answer-static-method"),
        (NotebookCellSelectorKind.SOURCE_MARKER, "TPSTUDIO: gravity_comparison"),
    ],
)
def test_all_selector_kinds_preserve_exact_values(kind, value) -> None:
    selector = NotebookCellSelector(kind, f"  {value}  ")
    assert selector.kind is kind
    assert selector.value == f"  {value}  "


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_selector_rejects_empty_or_blank_value(value: str) -> None:
    with pytest.raises(ValueError):
        _selector(value)


def test_selector_rejects_invalid_types_and_has_exact_equality() -> None:
    with pytest.raises(TypeError):
        NotebookCellSelector("tag", "answer")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        NotebookCellSelector(NotebookCellSelectorKind.TAG, 1)  # type: ignore[arg-type]
    assert _selector() == _selector()
    assert _selector() != _selector(kind=NotebookCellSelectorKind.CELL_ID)
    assert _selector() != _selector("Answer-gravity-dynamic")


def test_text_scope_rules_and_convenience_constructors() -> None:
    full = CellTextScope.full_source()
    after = CellTextScope.after_marker("  Réponse :  ")
    assert full == CellTextScope(CellTextScopeKind.FULL_SOURCE)
    assert full.marker is None
    assert after == CellTextScope(CellTextScopeKind.AFTER_MARKER, "  Réponse :  ")
    assert after.marker == "  Réponse :  "


def test_full_source_rejects_marker() -> None:
    with pytest.raises(ValueError):
        CellTextScope(CellTextScopeKind.FULL_SOURCE, "Réponse :")


@pytest.mark.parametrize("marker", [None, "", "   "])
def test_after_marker_requires_non_blank_marker(marker) -> None:
    error = TypeError if marker is None else ValueError
    with pytest.raises(error):
        CellTextScope(CellTextScopeKind.AFTER_MARKER, marker)


def test_scope_rejects_invalid_kind() -> None:
    with pytest.raises(TypeError):
        CellTextScope("full_source")  # type: ignore[arg-type]


@pytest.mark.parametrize("field_name", ["id", "production_id"])
@pytest.mark.parametrize("value", ["", "   "])
def test_binding_rejects_blank_identifiers(field_name: str, value: str) -> None:
    values = {
        "id": "dynamic-answer",
        "production_id": "gravity_dynamic",
        "selector": _selector(),
        "text_scope": CellTextScope.full_source(),
    }
    values[field_name] = value
    with pytest.raises(ValueError):
        CellProductionBinding(**values)  # type: ignore[arg-type]


def test_binding_validates_component_types_and_preserves_description() -> None:
    with pytest.raises(TypeError):
        _binding("id", "gravity_dynamic", selector="tag")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _binding("id", "gravity_dynamic", scope="full")  # type: ignore[arg-type]
    binding = CellProductionBinding(
        "  id  ", "  gravity_dynamic  ", _selector(),
        CellTextScope.full_source(), "  libre  "
    )
    assert binding.id == "  id  "
    assert binding.production_id == "  gravity_dynamic  "
    assert binding.description == "  libre  "


def test_all_four_models_are_immutable() -> None:
    selector = _selector()
    scope = CellTextScope.full_source()
    binding = _binding("id", "gravity_dynamic", selector, scope)
    plan = NotebookBindingPlan("bindings", "Bindings", _pendulum_plan(), (binding,))
    for instance, attribute in (
        (selector, "value"), (scope, "marker"),
        (binding, "description"), (plan, "title"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(instance, attribute, "changed")


def test_plan_converts_bindings_to_tuple_and_preserves_order() -> None:
    first = _binding("first", "gravity_dynamic")
    second = _binding("second", "gravity_static", _selector("static"))
    plan = NotebookBindingPlan(
        "bindings", "Bindings", _pendulum_plan(), [first, second]  # type: ignore[arg-type]
    )
    assert plan.bindings == (first, second)
    assert tuple(plan) == (first, second)
    assert len(plan) == 2


@pytest.mark.parametrize(("identifier", "title"), [("", "Title"), ("  ", "Title"), ("id", ""), ("id", "  ")])
def test_plan_rejects_blank_identity(identifier: str, title: str) -> None:
    with pytest.raises(ValueError):
        NotebookBindingPlan(identifier, title, _pendulum_plan(), (_binding("b", "gravity_dynamic"),))


def test_plan_rejects_empty_invalid_and_duplicate_binding_ids() -> None:
    production_plan = _pendulum_plan()
    with pytest.raises(ValueError):
        NotebookBindingPlan("id", "Title", production_plan, ())
    with pytest.raises(TypeError):
        NotebookBindingPlan("id", "Title", production_plan, (object(),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="identifiants"):
        NotebookBindingPlan("id", "Title", production_plan, (
            _binding("same", "gravity_dynamic"),
            _binding("same", "gravity_static", _selector("static")),
        ))


def test_plan_rejects_unknown_production_and_strict_duplicate() -> None:
    production_plan = _pendulum_plan()
    with pytest.raises(ValueError, match="inconnue"):
        NotebookBindingPlan("id", "Title", production_plan, (_binding("b", "unknown"),))
    first = _binding("first", "gravity_dynamic")
    duplicate = _binding("second", "gravity_dynamic")
    with pytest.raises(ValueError, match="dupliquée"):
        NotebookBindingPlan("id", "Title", production_plan, (first, duplicate))


def test_many_to_many_cardinalities_and_different_scopes_are_allowed() -> None:
    shared = _selector("shared-cell", NotebookCellSelectorKind.CELL_ID)
    bindings = (
        _binding("dynamic-result", "gravity_dynamic", shared),
        _binding("dynamic-detail", "gravity_dynamic", shared, CellTextScope.after_marker("Réponse :")),
        _binding("justification", "uncertainty_justification", shared),
        _binding("dynamic-other", "gravity_dynamic", _selector("other-cell", NotebookCellSelectorKind.CELL_ID)),
    )
    plan = NotebookBindingPlan("id", "Title", _pendulum_plan(), bindings)
    assert plan.for_selector(shared) == bindings[:3]
    assert plan.for_production("gravity_dynamic") == (bindings[0], bindings[1], bindings[3])


def test_lookup_methods_and_known_unbound_production() -> None:
    binding = _binding("dynamic", "gravity_dynamic")
    plan = NotebookBindingPlan("id", "Title", _pendulum_plan(), (binding,))
    assert plan.get("dynamic") is binding
    assert plan.get("unknown") is None
    assert plan.for_production("gravity_static") == ()
    assert plan.for_selector(_selector("unused")) == ()
    with pytest.raises(ValueError, match="inconnue"):
        plan.for_production("unknown")
    with pytest.raises(TypeError):
        plan.for_selector("tag")  # type: ignore[arg-type]


def test_evaluation_order_follows_dependencies_and_binding_declaration_order() -> None:
    bindings = (
        _binding("comparison", "gravity_comparison", _selector("comparison")),
        _binding("dynamic-first", "gravity_dynamic"),
        _binding("static", "gravity_static", _selector("static")),
        _binding("dynamic-second", "gravity_dynamic", _selector("dynamic-2")),
        _binding("plot", "period_plot", _selector("plot")),
        _binding("final", "final_interpretation", _selector("final")),
    )
    plan = NotebookBindingPlan("id", "Title", _pendulum_plan(), bindings)
    assert tuple(item.id for item in plan.in_evaluation_order) == (
        "plot", "dynamic-first", "dynamic-second", "static", "comparison", "final"
    )


def test_contract_stores_no_notebook_runtime_data() -> None:
    names = {
        field.name
        for model in (NotebookCellSelector, CellTextScope, CellProductionBinding, NotebookBindingPlan)
        for field in fields(model)
    }
    assert not names & {
        "path", "notebook_path", "source", "cell_content", "cell_index", "index",
        "outputs", "execution_result", "resolution_status", "diagnostic", "metadata",
    }
