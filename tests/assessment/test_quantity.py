from dataclasses import FrozenInstanceError, fields, replace

import pytest

import tpstudio.assessment.quantity as quantity_module
from tpstudio.assessment import (
    QuantityAssessmentPipeline,
    QuantityAssessmentResult,
    assess_quantity_text,
)
from tpstudio.diagnostics import QuantityDiagnosticCode
from tpstudio.expectations import (
    EvaluationBasis,
    ExpectedQuantity,
    PresenceRequirement,
    QuantityExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
    UncertaintyQualityExpectationSet,
    UncertaintyQualitySpec,
)
from tpstudio.feedback import (
    QuantityFeedbackCatalog,
    QuantityFeedbackTemplate,
    french_quantity_feedback_catalog,
)


def _quantity_set(
    *,
    justification: PresenceRequirement = PresenceRequirement.IGNORE,
    production_id: str = "gravity_dynamic",
) -> QuantityExpectationSet:
    production = ScientificProductionSpec(
        production_id,
        "Accélération de la pesanteur",
        ScientificProductionKind.QUANTITY,
        (EvaluationBasis.STRUCTURAL,),
        required=True,
    )
    plan = ScientificProductionPlan("pendulum", "Pendule", (production,))
    expectation = ExpectedQuantity(
        production_id,
        "g",
        canonical_unit="m·s⁻²",
        unit_requirement=PresenceRequirement.REQUIRED,
        uncertainty_requirement=PresenceRequirement.REQUIRED,
        uncertainty_justification_requirement=justification,
    )
    return QuantityExpectationSet(plan, (expectation,))


def _policy(
    quantity_set: QuantityExpectationSet,
    *,
    production_id: str = "gravity_dynamic",
) -> UncertaintyQualityExpectationSet:
    return UncertaintyQualityExpectationSet(
        quantity_set,
        (
            UncertaintyQualitySpec(
                production_id,
                require_strictly_positive=True,
                allowed_significant_digits=(1, 2),
                require_matching_decimal_place=True,
            ),
        ),
    )


def _assess(
    text: str,
    *,
    justification: PresenceRequirement = PresenceRequirement.IGNORE,
    catalog=True,
) -> QuantityAssessmentResult:
    quantity_set = _quantity_set(justification=justification)
    return assess_quantity_text(
        text,
        "gravity_dynamic",
        quantity_set,
        _policy(quantity_set),
        french_quantity_feedback_catalog() if catalog else None,
    )


def _codes(result: QuantityAssessmentResult) -> tuple[QuantityDiagnosticCode, ...]:
    return tuple(item.code for item in result.diagnostics)


def test_complete_chain_is_auditable_and_immutable() -> None:
    result = _assess("g = (9,7 ± 0,4) m·s⁻²")
    assert result.expectation is result.quantity_expectation_set.get(result.production_id)
    assert result.detection.expectation is result.expectation
    assert result.structural_evaluation.detection is result.detection
    assert result.structural_evaluation.expectation_set is result.quantity_expectation_set
    assert result.uncertainty_evaluation is not None
    assert result.uncertainty_evaluation.structural_evaluation is result.structural_evaluation
    assert result.diagnostic_set.structural_evaluation is result.structural_evaluation
    assert result.diagnostic_set.uncertainty_evaluation is result.uncertainty_evaluation
    assert result.feedback_set is not None
    assert result.feedback_set.diagnostic_set is result.diagnostic_set
    with pytest.raises(FrozenInstanceError):
        result.expectation = result.expectation  # type: ignore[misc]


def test_properties_for_complete_satisfied_answer() -> None:
    result = _assess("g = (9,7 ± 0,4) m·s⁻²")
    assert result.production_id == "gravity_dynamic"
    assert result.production_spec is result.quantity_expectation_set.plan.get(result.production_id)
    assert result.selected_observation is result.structural_evaluation.selected_observation
    assert result.has_observation
    assert result.is_structurally_satisfied
    assert not result.has_failures
    assert not result.has_deferred
    assert result.diagnostics == ()
    assert result.student_feedback == ()
    assert result.teacher_feedback == ()
    assert not result.has_student_feedback
    assert not result.has_teacher_feedback
    assert result.feedback_set is not None and result.feedback_set.is_empty


def test_result_does_not_store_complete_source_text_or_forbidden_metadata() -> None:
    names = {field.name for field in fields(QuantityAssessmentResult)}
    assert names == {
        "quantity_expectation_set", "expectation", "detection",
        "structural_evaluation", "uncertainty_evaluation",
        "diagnostic_set", "feedback_set",
    }
    assert not names & {"source_text", "raw_text", "cell_content", "notebook_path", "metadata"}


@pytest.mark.parametrize(
    ("text", "code", "feedback"),
    [
        ("g = 9,7 ± 0,4", QuantityDiagnosticCode.UNIT_MISSING, "Précisez l’unité de la valeur indiquée."),
        ("g = 9,7 m·s⁻²", QuantityDiagnosticCode.UNCERTAINTY_MISSING, "Précisez l’incertitude associée à cette valeur."),
        ("g = (9,7 ± -0,4) m·s⁻²", QuantityDiagnosticCode.UNCERTAINTY_NOT_STRICTLY_POSITIVE, "L’incertitude doit être strictement positive."),
        ("g = (9,7 ± 0,444) m·s⁻²", QuantityDiagnosticCode.UNCERTAINTY_SIGNIFICANT_DIGITS_INVALID, "Le nombre de chiffres significatifs de l’incertitude n’est pas conforme à la consigne."),
        ("g = (9,70 ± 0,4) m·s⁻²", QuantityDiagnosticCode.UNCERTAINTY_DECIMAL_PLACE_MISMATCH, "Présentez la valeur et son incertitude au même rang décimal."),
        ("La mesure a été réalisée correctement.", QuantityDiagnosticCode.QUANTITY_MISSING, "La grandeur attendue n’a pas été fournie."),
    ],
)
def test_business_failures_are_delegated_to_existing_components(text, code, feedback) -> None:
    result = _assess(text)
    assert code in _codes(result)
    assert feedback in tuple(item.text for item in result.student_feedback)


def test_missing_uncertainty_has_no_quality_double_penalty() -> None:
    result = _assess("g = 9,7 m·s⁻²")
    assert _codes(result) == (QuantityDiagnosticCode.UNCERTAINTY_MISSING,)
    assert result.uncertainty_evaluation is not None
    assert not result.uncertainty_evaluation.is_applicable


def test_missing_quantity_exposes_no_observation() -> None:
    result = _assess("La mesure a été réalisée correctement.")
    assert result.selected_observation is None
    assert not result.has_observation


def test_required_justification_is_deferred_for_teacher_only() -> None:
    result = _assess(
        "g = (9,7 ± 0,4) m·s⁻²",
        justification=PresenceRequirement.REQUIRED,
    )
    assert _codes(result) == (QuantityDiagnosticCode.UNCERTAINTY_JUSTIFICATION_DEFERRED,)
    assert result.has_deferred and not result.has_failures
    assert result.student_feedback == ()
    assert tuple(item.text for item in result.teacher_feedback) == (
        "La justification de l’incertitude doit encore être vérifiée.",
    )


def test_no_catalog_keeps_diagnostics_and_returns_empty_feedback_properties() -> None:
    result = _assess("g = 9,7 ± 0,4", catalog=False)
    assert _codes(result) == (QuantityDiagnosticCode.UNIT_MISSING,)
    assert result.feedback_set is None
    assert result.student_feedback == () and result.teacher_feedback == ()


def test_incomplete_catalog_renders_only_configured_diagnostics() -> None:
    catalog = QuantityFeedbackCatalog(
        "partial", "Partiel",
        (QuantityFeedbackTemplate(QuantityDiagnosticCode.UNIT_MISSING, "Unité."),),
    )
    quantity_set = _quantity_set()
    result = assess_quantity_text(
        "g = 9,7", "gravity_dynamic", quantity_set, _policy(quantity_set), catalog
    )
    assert _codes(result) == (
        QuantityDiagnosticCode.UNIT_MISSING,
        QuantityDiagnosticCode.UNCERTAINTY_MISSING,
    )
    assert tuple(item.text for item in result.student_feedback) == ("Unité.",)


def test_no_uncertainty_policy_still_builds_structural_diagnostics() -> None:
    quantity_set = _quantity_set()
    result = assess_quantity_text("g = 9,7", "gravity_dynamic", quantity_set)
    assert result.uncertainty_evaluation is None
    assert _codes(result) == (
        QuantityDiagnosticCode.UNIT_MISSING,
        QuantityDiagnosticCode.UNCERTAINTY_MISSING,
    )


def test_policy_without_requested_production_is_valid() -> None:
    first = ScientificProductionSpec("gravity_dynamic", "g dynamique", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    second = ScientificProductionSpec("gravity_static", "g statique", ScientificProductionKind.QUANTITY, (EvaluationBasis.STRUCTURAL,))
    plan = ScientificProductionPlan("p", "Pendule", (first, second))
    quantities = QuantityExpectationSet(plan, (
        ExpectedQuantity("gravity_dynamic", "g", canonical_unit="m·s⁻²", uncertainty_requirement=PresenceRequirement.REQUIRED),
        ExpectedQuantity("gravity_static", "g", canonical_unit="m·s⁻²", uncertainty_requirement=PresenceRequirement.REQUIRED),
    ))
    policy = _policy(quantities, production_id="gravity_static")
    result = assess_quantity_text("g = 9,7", "gravity_dynamic", quantities, policy)
    assert result.uncertainty_evaluation is None
    assert all(code.source.value == "structure" for code in _codes(result))


@pytest.mark.parametrize("production_id", ["", "   "])
def test_blank_production_id_is_rejected(production_id: str) -> None:
    with pytest.raises(ValueError):
        assess_quantity_text("g=9", production_id, _quantity_set())


def test_unknown_production_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="inconnue"):
        assess_quantity_text("g=9", "unknown", _quantity_set())


def test_incoherent_uncertainty_quantity_set_is_rejected_by_identity() -> None:
    quantity_set = _quantity_set()
    equivalent_set = _quantity_set()
    with pytest.raises(ValueError, match="partager le même jeu"):
        assess_quantity_text("g=9", "gravity_dynamic", quantity_set, _policy(equivalent_set))


@pytest.mark.parametrize(
    "arguments",
    [
        (1, "gravity_dynamic", _quantity_set(), None, None),
        ("g=9", 1, _quantity_set(), None, None),
        ("g=9", "gravity_dynamic", object(), None, None),
        ("g=9", "gravity_dynamic", _quantity_set(), object(), None),
        ("g=9", "gravity_dynamic", _quantity_set(), None, object()),
    ],
)
def test_pipeline_validates_argument_types(arguments) -> None:
    with pytest.raises(TypeError):
        QuantityAssessmentPipeline().assess(*arguments)


def test_convenience_function_only_delegates(monkeypatch) -> None:
    sentinel = object()
    calls = []
    def fake_assess(self, *args):
        calls.append(args)
        return sentinel
    monkeypatch.setattr(QuantityAssessmentPipeline, "assess", fake_assess)
    quantity_set = _quantity_set()
    assert assess_quantity_text("g=9", "gravity_dynamic", quantity_set) is sentinel
    assert calls == [("g=9", "gravity_dynamic", quantity_set, None, None)]


def test_pipeline_calls_each_conceptual_stage_once(monkeypatch) -> None:
    quantity_set = _quantity_set()
    policy = _policy(quantity_set)
    catalog = french_quantity_feedback_catalog()
    names = (
        "extract_expected_quantity", "evaluate_quantity_structure",
        "evaluate_quantity_uncertainty", "build_quantity_diagnostics",
        "render_quantity_feedback",
    )
    originals = {name: getattr(quantity_module, name) for name in names}
    calls = {name: 0 for name in names}
    for name in names:
        def wrapper(*args, _name=name, **kwargs):
            calls[_name] += 1
            return originals[_name](*args, **kwargs)
        monkeypatch.setattr(quantity_module, name, wrapper)
    QuantityAssessmentPipeline().assess(
        "g=(9,7 ± 0,4) m·s⁻²", "gravity_dynamic", quantity_set, policy, catalog
    )
    assert calls == {name: 1 for name in names}


def test_result_rejects_every_foreign_link() -> None:
    result = _assess("g=(9,7 ± 0,4) m·s⁻²")
    foreign = _assess("g=(9,7 ± 0,4) m·s⁻²")
    fields_to_replace = (
        ("expectation", foreign.expectation),
        ("detection", foreign.detection),
        ("structural_evaluation", foreign.structural_evaluation),
        ("uncertainty_evaluation", foreign.uncertainty_evaluation),
        ("diagnostic_set", foreign.diagnostic_set),
        ("feedback_set", foreign.feedback_set),
    )
    for field_name, value in fields_to_replace:
        with pytest.raises(ValueError):
            replace(result, **{field_name: value})


def test_public_api_preserves_the_three_quantity_assessment_objects() -> None:
    import tpstudio.assessment as assessment
    assert [name for name in assessment.__all__ if name in {
        "QuantityAssessmentPipeline", "QuantityAssessmentResult", "assess_quantity_text"
    }] == [
        "QuantityAssessmentPipeline", "QuantityAssessmentResult", "assess_quantity_text"
    ]
    assert not hasattr(QuantityAssessmentResult, "score")
    assert not hasattr(QuantityAssessmentResult, "correct")
