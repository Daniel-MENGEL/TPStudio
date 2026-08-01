from dataclasses import FrozenInstanceError
import inspect

import pytest

import tpstudio.expectations.scientific_productions as production_models
from tpstudio.expectations import (
    EvaluationBasis,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
)


def _spec(
    identifier: str,
    *,
    kind: ScientificProductionKind = ScientificProductionKind.QUANTITY,
    bases: tuple[EvaluationBasis, ...] = (EvaluationBasis.STRUCTURAL,),
    depends_on: tuple[str, ...] = (),
) -> ScientificProductionSpec:
    return ScientificProductionSpec(
        identifier,
        f"Production {identifier}",
        kind,
        bases,
        depends_on=depends_on,
    )


def test_enum_values_are_stable_and_complete() -> None:
    assert tuple(item.value for item in ScientificProductionKind) == (
        "relation",
        "interpretation",
        "quantity",
        "plot",
        "comparison",
        "justification",
    )
    assert tuple(item.value for item in EvaluationBasis) == (
        "declared_content",
        "fixed_reference",
        "submission_derived",
        "cross_production",
        "structural",
        "semantic",
    )


def test_spec_is_immutable_and_normalizes_public_collections_to_tuples() -> None:
    spec = ScientificProductionSpec(
        "gravity",
        "Gravity",
        ScientificProductionKind.QUANTITY,
        [EvaluationBasis.STRUCTURAL],  # type: ignore[arg-type]
        depends_on=["plot"],  # type: ignore[arg-type]
    )

    assert spec.evaluation_bases == (EvaluationBasis.STRUCTURAL,)
    assert spec.depends_on == ("plot",)
    with pytest.raises(FrozenInstanceError):
        spec.label = "Changed"  # type: ignore[misc]


def test_spec_stably_deduplicates_bases_and_dependencies() -> None:
    spec = ScientificProductionSpec(
        "comparison",
        "Comparison",
        ScientificProductionKind.COMPARISON,
        (
            EvaluationBasis.CROSS_PRODUCTION,
            EvaluationBasis.SEMANTIC,
            EvaluationBasis.CROSS_PRODUCTION,
        ),
        depends_on=("static", "dynamic", "static"),
    )

    assert spec.evaluation_bases == (
        EvaluationBasis.CROSS_PRODUCTION,
        EvaluationBasis.SEMANTIC,
    )
    assert spec.depends_on == ("static", "dynamic")


def test_spec_preserves_significant_strings_exactly() -> None:
    spec = ScientificProductionSpec(
        "  gravity  ",
        "  Valeur de g  ",
        ScientificProductionKind.QUANTITY,
        (EvaluationBasis.FIXED_REFERENCE,),
        description="  intention pédagogique  ",
    )

    assert spec.id == "  gravity  "
    assert spec.label == "  Valeur de g  "
    assert spec.description == "  intention pédagogique  "


@pytest.mark.parametrize(
    ("identifier", "label"),
    (("", "Label"), ("   ", "Label"), ("id", ""), ("id", "  ")),
)
def test_spec_rejects_blank_identifier_or_label(
    identifier: str,
    label: str,
) -> None:
    with pytest.raises(ValueError, match="ne peut pas être vide"):
        ScientificProductionSpec(
            identifier,
            label,
            ScientificProductionKind.QUANTITY,
            (EvaluationBasis.STRUCTURAL,),
        )


def test_spec_rejects_empty_or_invalid_evaluation_bases() -> None:
    with pytest.raises(ValueError, match="au moins une base"):
        ScientificProductionSpec(
            "id", "Label", ScientificProductionKind.QUANTITY, ()
        )
    with pytest.raises(TypeError, match="EvaluationBasis"):
        ScientificProductionSpec(
            "id",
            "Label",
            ScientificProductionKind.QUANTITY,
            ("structural",),  # type: ignore[arg-type]
        )


def test_spec_rejects_invalid_kind() -> None:
    with pytest.raises(TypeError, match="ScientificProductionKind"):
        ScientificProductionSpec(
            "id",
            "Label",
            "quantity",  # type: ignore[arg-type]
            (EvaluationBasis.STRUCTURAL,),
        )


def test_spec_rejects_blank_and_self_dependencies() -> None:
    with pytest.raises(ValueError, match="dépendance ne peut pas être vide"):
        _spec("id", depends_on=("  ",))
    with pytest.raises(ValueError, match="elle-même"):
        _spec("id", depends_on=("id",))


def test_plan_is_immutable_converts_to_tuple_and_preserves_declaration_order() -> None:
    first = _spec("first")
    second = _spec("second")
    plan = ScientificProductionPlan(
        "plan",
        "Plan",
        [first, second],  # type: ignore[arg-type]
    )

    assert plan.productions == (first, second)
    assert tuple(plan) == (first, second)
    assert len(plan) == 2
    with pytest.raises(FrozenInstanceError):
        plan.title = "Changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("identifier", "title"),
    (("", "Title"), ("  ", "Title"), ("id", ""), ("id", "   ")),
)
def test_plan_rejects_blank_identifier_or_title(
    identifier: str,
    title: str,
) -> None:
    with pytest.raises(ValueError, match="ne peut pas être vide"):
        ScientificProductionPlan(identifier, title, (_spec("production"),))


def test_plan_rejects_empty_or_duplicate_productions() -> None:
    with pytest.raises(ValueError, match="ne peut pas être vide"):
        ScientificProductionPlan("plan", "Plan", ())
    with pytest.raises(ValueError, match="doivent être uniques"):
        ScientificProductionPlan("plan", "Plan", (_spec("same"), _spec("same")))


def test_plan_rejects_unknown_dependency() -> None:
    with pytest.raises(ValueError, match="inconnue"):
        ScientificProductionPlan(
            "plan",
            "Plan",
            (_spec("consumer", depends_on=("missing",)),),
        )


def test_plan_rejects_direct_dependency_cycle() -> None:
    with pytest.raises(ValueError, match="cycle"):
        ScientificProductionPlan(
            "plan",
            "Plan",
            (
                _spec("a", depends_on=("b",)),
                _spec("b", depends_on=("a",)),
            ),
        )


def test_plan_rejects_indirect_dependency_cycle() -> None:
    with pytest.raises(ValueError, match="cycle"):
        ScientificProductionPlan(
            "plan",
            "Plan",
            (
                _spec("a", depends_on=("b",)),
                _spec("b", depends_on=("c",)),
                _spec("c", depends_on=("a",)),
            ),
        )


def test_plan_get_returns_known_production_or_none() -> None:
    production = _spec("gravity")
    plan = ScientificProductionPlan("plan", "Plan", (production,))

    assert plan.get("gravity") is production
    assert plan.get("unknown") is None


def test_evaluation_order_preserves_independent_declaration_order() -> None:
    productions = (_spec("a"), _spec("b"), _spec("c"))
    plan = ScientificProductionPlan("plan", "Plan", productions)

    assert plan.evaluation_order == productions
    assert plan.evaluation_order == plan.evaluation_order


def test_evaluation_order_places_dependency_before_consumer() -> None:
    consumer = _spec("consumer", depends_on=("source",))
    source = _spec("source")
    plan = ScientificProductionPlan("plan", "Plan", (consumer, source))

    assert plan.evaluation_order == (source, consumer)


def test_evaluation_order_is_stable_with_multiple_dependencies() -> None:
    comparison = _spec(
        "comparison",
        kind=ScientificProductionKind.COMPARISON,
        depends_on=("measure_a", "measure_b"),
    )
    measure_a = _spec("measure_a")
    measure_b = _spec("measure_b")
    interpretation = _spec(
        "interpretation", kind=ScientificProductionKind.INTERPRETATION
    )
    plan = ScientificProductionPlan(
        "plan",
        "Plan",
        (comparison, measure_a, measure_b, interpretation),
    )

    assert plan.evaluation_order == (
        measure_a,
        measure_b,
        comparison,
        interpretation,
    )


def test_production_models_have_no_reasoning_or_external_dependency() -> None:
    source = inspect.getsource(production_models)

    assert "tpstudio.reasoning" not in source
    assert "numpy" not in source.lower()
    assert "sympy" not in source.lower()
    assert "matplotlib" not in source.lower()
    assert "openai" not in source.lower()
