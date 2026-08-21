from decimal import Decimal
from dataclasses import replace

import pytest

from tpstudio.expectations import (
    Add,
    DerivedQuantityExpectationSet,
    EvaluationBasis,
    ExpectedDerivedQuantity,
    OperandRef,
    ProductionValue,
    RegressionParameter,
    RegressionParameterKind,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
    TeacherConstant,
)
from tpstudio.projects.thin_lens import thin_lens_teacher_project


def _plan():
    return ScientificProductionPlan(
        "opaque", "Opaque",
        (
            ScientificProductionSpec("p1", "p1", ScientificProductionKind.QUANTITY, (EvaluationBasis.SUBMISSION_DERIVED,)),
            ScientificProductionSpec("p2", "p2", ScientificProductionKind.PLOT, (EvaluationBasis.SUBMISSION_DERIVED,)),
            ScientificProductionSpec("p3", "p3", ScientificProductionKind.QUANTITY, (EvaluationBasis.SUBMISSION_DERIVED,)),
        ),
    )


def _expectation(target="p3", source_id="p1"):
    source = ProductionValue(source_id)
    return ExpectedDerivedQuantity(target, "q", (source,), OperandRef(source))


def test_empty_set_is_immutable_and_lookup_is_empty():
    expectations = DerivedQuantityExpectationSet()
    assert tuple(expectations) == ()
    assert expectations.get("p3") is None
    assert expectations.by_production_id("p3") is None


def test_set_validates_unique_targets_and_lookup():
    first = _expectation()
    expectations = DerivedQuantityExpectationSet((first,))
    assert expectations.get("p3") is first
    with pytest.raises(ValueError, match="uniques"):
        DerivedQuantityExpectationSet((first, _expectation()))


def test_set_rejects_non_derived_expectation():
    with pytest.raises(TypeError):
        DerivedQuantityExpectationSet((object(),))


def test_teacher_constant_can_be_stored_with_derived_sources():
    source = TeacherConstant("k", Decimal("4"))
    expectation = ExpectedDerivedQuantity("p3", "q", (source,), OperandRef(source))
    assert DerivedQuantityExpectationSet((expectation,)).get("p3") is expectation


def test_existing_configuration_accepts_empty_and_valid_derived_set():
    project = thin_lens_teacher_project()
    assert len(project.derived_quantity_expectation_set) == 0
    source = ProductionValue("conjugation_slope")
    expectation = ExpectedDerivedQuantity(
        "focal_intercept", "f", (source,), OperandRef(source)
    )
    configured = replace(
        project,
        derived_quantity_expectation_set=DerivedQuantityExpectationSet((expectation,)),
    )
    assert configured.derived_quantity_expectation_set.get("focal_intercept") is expectation


def test_configuration_rejects_invalid_derived_source_kind_and_target_kind():
    project = thin_lens_teacher_project()
    source = RegressionParameter("conjugation_slope", RegressionParameterKind.INTERCEPT)
    invalid_source = ExpectedDerivedQuantity(
        "focal_intercept", "f", (source,), OperandRef(source)
    )
    with pytest.raises(ValueError, match="Attentes dérivées invalides"):
        replace(
            project,
            derived_quantity_expectation_set=DerivedQuantityExpectationSet((invalid_source,)),
        )

    source = ProductionValue("conjugation_slope")
    invalid_target = ExpectedDerivedQuantity(
        "conjugation_graph", "g", (source,), OperandRef(source)
    )
    with pytest.raises(ValueError, match="Attentes dérivées invalides"):
        replace(
            project,
            derived_quantity_expectation_set=DerivedQuantityExpectationSet((invalid_target,)),
        )
