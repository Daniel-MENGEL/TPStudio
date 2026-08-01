from dataclasses import FrozenInstanceError, replace

import pytest

from tpstudio.diagnostics import (
    QuantityDiagnostic,
    QuantityDiagnosticCode,
    build_quantity_diagnostics,
)
from tpstudio.evaluation import (
    evaluate_quantity_structure,
    evaluate_quantity_uncertainty,
)
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
    FeedbackAudience,
    FeedbackPriority,
    QuantityFeedbackCatalog,
    QuantityFeedbackItem,
    QuantityFeedbackRenderer,
    QuantityFeedbackSet,
    QuantityFeedbackTemplate,
    french_quantity_feedback_catalog,
    render_quantity_feedback,
)
from tpstudio.reasoning import extract_expected_quantity


def _diagnostics(
    text: str,
    *,
    required: bool = True,
    justification: PresenceRequirement = PresenceRequirement.IGNORE,
):
    production = ScientificProductionSpec(
        "gravity",
        "Accélération de la pesanteur",
        ScientificProductionKind.QUANTITY,
        (EvaluationBasis.STRUCTURAL,),
        required=required,
    )
    plan = ScientificProductionPlan("pendulum", "Pendule", (production,))
    quantity = ExpectedQuantity(
        "gravity",
        "g",
        canonical_unit="m·s⁻²",
        unit_requirement=PresenceRequirement.REQUIRED,
        uncertainty_requirement=PresenceRequirement.REQUIRED,
        uncertainty_justification_requirement=justification,
    )
    quantity_set = QuantityExpectationSet(plan, (quantity,))
    structural = evaluate_quantity_structure(
        extract_expected_quantity(text, quantity), quantity_set
    )
    policy = UncertaintyQualityExpectationSet(
        quantity_set, (UncertaintyQualitySpec("gravity"),)
    )
    quality = evaluate_quantity_uncertainty(structural, policy)
    return build_quantity_diagnostics(structural, quality)


def _catalog(*templates: QuantityFeedbackTemplate) -> QuantityFeedbackCatalog:
    return QuantityFeedbackCatalog("test", "Catalogue de test", templates)


def _template(
    code: QuantityDiagnosticCode,
    text: str = "Texte configuré.",
    *,
    audience: FeedbackAudience = FeedbackAudience.STUDENT,
    priority: FeedbackPriority = FeedbackPriority.NORMAL,
) -> QuantityFeedbackTemplate:
    return QuantityFeedbackTemplate(code, text, audience, priority)


def test_enum_values() -> None:
    assert [item.value for item in FeedbackAudience] == ["student", "teacher"]
    assert [item.value for item in FeedbackPriority] == ["low", "normal", "high"]


def test_all_models_are_immutable() -> None:
    catalog = french_quantity_feedback_catalog()
    result = render_quantity_feedback(_diagnostics("g=9"), catalog)
    with pytest.raises(FrozenInstanceError):
        catalog.title = "Autre"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        catalog.templates[0].text = "Autre"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.items = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.items[0].production_label = "Autre"  # type: ignore[misc]


@pytest.mark.parametrize("text", ["", "   "])
def test_template_rejects_empty_or_blank_text(text: str) -> None:
    with pytest.raises(ValueError):
        _template(QuantityDiagnosticCode.UNIT_MISSING, text)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"diagnostic_code": "unit_missing"},
        {"audience": "student"},
        {"priority": "normal"},
    ],
)
def test_template_requires_exact_enum_types(kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "diagnostic_code": QuantityDiagnosticCode.UNIT_MISSING,
        "text": "Texte",
        "audience": FeedbackAudience.STUDENT,
        "priority": FeedbackPriority.NORMAL,
    }
    values.update(kwargs)
    with pytest.raises(TypeError):
        QuantityFeedbackTemplate(**values)  # type: ignore[arg-type]


def test_template_preserves_exact_text_and_description() -> None:
    template = QuantityFeedbackTemplate(
        QuantityDiagnosticCode.UNIT_MISSING,
        "  Texte exact.  ",
        description="  interne  ",
    )
    assert template.text == "  Texte exact.  "
    assert template.description == "  interne  "


def test_deferred_justification_is_for_teacher_only() -> None:
    with pytest.raises(ValueError):
        _template(QuantityDiagnosticCode.UNCERTAINTY_JUSTIFICATION_DEFERRED)
    template = _template(
        QuantityDiagnosticCode.UNCERTAINTY_JUSTIFICATION_DEFERRED,
        audience=FeedbackAudience.TEACHER,
    )
    assert template.audience is FeedbackAudience.TEACHER


@pytest.mark.parametrize("field", ["id", "title"])
@pytest.mark.parametrize("value", ["", "   "])
def test_catalog_rejects_blank_identity_fields(field: str, value: str) -> None:
    values = {
        "id": "catalog",
        "title": "Catalogue",
        "templates": (_template(QuantityDiagnosticCode.UNIT_MISSING),),
    }
    values[field] = value
    with pytest.raises(ValueError):
        QuantityFeedbackCatalog(**values)  # type: ignore[arg-type]


def test_catalog_rejects_empty_and_duplicate_templates() -> None:
    with pytest.raises(ValueError):
        QuantityFeedbackCatalog("empty", "Vide", ())
    template = _template(QuantityDiagnosticCode.UNIT_MISSING)
    with pytest.raises(ValueError):
        QuantityFeedbackCatalog("duplicate", "Doublon", (template, template))


def test_catalog_converts_templates_and_preserves_order_and_metadata() -> None:
    first = _template(QuantityDiagnosticCode.UNCERTAINTY_MISSING)
    second = _template(QuantityDiagnosticCode.UNIT_MISSING)
    catalog = QuantityFeedbackCatalog(
        " catalog ",
        " Catalogue ",
        [first, second],  # type: ignore[arg-type]
        language=" fr ",
        description="  description  ",
    )
    assert catalog.templates == (first, second)
    assert tuple(catalog) == (first, second)
    assert len(catalog) == 2
    assert catalog.language == " fr "
    assert catalog.description == "  description  "
    assert catalog.get(QuantityDiagnosticCode.UNIT_MISSING) is second
    assert catalog.get(QuantityDiagnosticCode.QUANTITY_MISSING) is None


def test_feedback_item_derives_all_public_information() -> None:
    diagnostic_set = _diagnostics("g=9")
    diagnostic = diagnostic_set.diagnostics[0]
    template = _template(
        diagnostic.code,
        "Message exact.",
        audience=FeedbackAudience.TEACHER,
        priority=FeedbackPriority.HIGH,
    )
    item = QuantityFeedbackItem(diagnostic, template, "Pesanteur")
    assert item.code is diagnostic.code
    assert item.production_id == "gravity"
    assert item.message_key == diagnostic.message_key
    assert item.text == "Message exact."
    assert item.audience is FeedbackAudience.TEACHER
    assert item.priority is FeedbackPriority.HIGH
    assert item.observation is diagnostic.observation
    assert item.status is diagnostic.status
    assert item.diagnostic is diagnostic


def test_feedback_item_validates_template_and_label() -> None:
    diagnostic = _diagnostics("g=9").diagnostics[0]
    wrong = _template(QuantityDiagnosticCode.UNCERTAINTY_MISSING)
    with pytest.raises(ValueError):
        QuantityFeedbackItem(diagnostic, wrong, "Pesanteur")
    with pytest.raises(ValueError):
        QuantityFeedbackItem(
            diagnostic, _template(diagnostic.code), "   "
        )


def test_empty_diagnostics_never_invent_positive_feedback() -> None:
    result = render_quantity_feedback(
        _diagnostics("g=(9,7 ± 0,4) m·s⁻²"),
        french_quantity_feedback_catalog(),
    )
    assert result.is_empty
    assert tuple(result) == ()
    assert not result.has_student_feedback
    assert not result.has_teacher_feedback


@pytest.mark.parametrize(
    ("text", "code", "expected_text", "priority", "has_observation"),
    [
        (
            "",
            QuantityDiagnosticCode.QUANTITY_MISSING,
            "La grandeur attendue n’a pas été fournie.",
            FeedbackPriority.HIGH,
            False,
        ),
        (
            "g=9 ± 1",
            QuantityDiagnosticCode.UNIT_MISSING,
            "Précisez l’unité de la valeur indiquée.",
            FeedbackPriority.NORMAL,
            True,
        ),
        (
            "g=9 m·s⁻²",
            QuantityDiagnosticCode.UNCERTAINTY_MISSING,
            "Précisez l’incertitude associée à cette valeur.",
            FeedbackPriority.HIGH,
            True,
        ),
        (
            "g=(9 ± 0) m·s⁻²",
            QuantityDiagnosticCode.UNCERTAINTY_NOT_STRICTLY_POSITIVE,
            "L’incertitude doit être strictement positive.",
            FeedbackPriority.HIGH,
            True,
        ),
        (
            "g=(9,700 ± 0,456) m·s⁻²",
            QuantityDiagnosticCode.UNCERTAINTY_SIGNIFICANT_DIGITS_INVALID,
            "Le nombre de chiffres significatifs de l’incertitude n’est pas conforme à la consigne.",
            FeedbackPriority.LOW,
            True,
        ),
        (
            "g=(9,70 ± 0,4) m·s⁻²",
            QuantityDiagnosticCode.UNCERTAINTY_DECIMAL_PLACE_MISMATCH,
            "Présentez la valeur et son incertitude au même rang décimal.",
            FeedbackPriority.LOW,
            True,
        ),
    ],
)
def test_french_student_feedback_cases(
    text: str,
    code: QuantityDiagnosticCode,
    expected_text: str,
    priority: FeedbackPriority,
    has_observation: bool,
) -> None:
    diagnostic_set = _diagnostics(text)
    result = render_quantity_feedback(
        diagnostic_set, french_quantity_feedback_catalog()
    )
    item = result.get(code)
    assert item is not None
    assert item.text == expected_text
    assert item.priority is priority
    assert item.audience is FeedbackAudience.STUDENT
    assert item.production_label == "Accélération de la pesanteur"
    assert (item.observation is not None) is has_observation
    if item.observation is not None:
        assert item.observation is diagnostic_set.selected_observation


def test_required_deferred_justification_is_teacher_feedback_only() -> None:
    result = render_quantity_feedback(
        _diagnostics(
            "g=(9,7 ± 0,4) m·s⁻²",
            justification=PresenceRequirement.REQUIRED,
        ),
        french_quantity_feedback_catalog(),
    )
    assert len(result) == 1
    assert result.student_items == ()
    assert result.teacher_items == result.items
    assert not result.has_student_feedback
    assert result.has_teacher_feedback
    assert result.items[0].text == (
        "La justification de l’incertitude doit encore être vérifiée."
    )


def test_student_failure_precedes_teacher_deferred_note() -> None:
    result = render_quantity_feedback(
        _diagnostics("g=(9 ± 0)", justification=PresenceRequirement.REQUIRED),
        french_quantity_feedback_catalog(),
    )
    assert [item.code for item in result] == [
        QuantityDiagnosticCode.UNIT_MISSING,
        QuantityDiagnosticCode.UNCERTAINTY_NOT_STRICTLY_POSITIVE,
        QuantityDiagnosticCode.UNCERTAINTY_JUSTIFICATION_DEFERRED,
    ]
    assert result.student_items == result.items[:2]
    assert result.teacher_items == result.items[2:]


def test_missing_catalog_code_means_no_feedback_without_fallback() -> None:
    result = render_quantity_feedback(
        _diagnostics("g=9"),
        _catalog(_template(QuantityDiagnosticCode.QUANTITY_MISSING)),
    )
    assert result.is_empty


def test_partial_catalog_only_renders_matching_diagnostic() -> None:
    result = render_quantity_feedback(
        _diagnostics("g=9"),
        _catalog(_template(QuantityDiagnosticCode.UNIT_MISSING)),
    )
    assert [item.code for item in result] == [QuantityDiagnosticCode.UNIT_MISSING]


def test_custom_wording_audience_and_priority_do_not_modify_diagnostic() -> None:
    diagnostic_set = _diagnostics("g=9 ± 1")
    diagnostic = diagnostic_set.diagnostics[0]
    catalog = _catalog(
        _template(
            QuantityDiagnosticCode.UNIT_MISSING,
            "Contrôle interne personnalisé.",
            audience=FeedbackAudience.TEACHER,
            priority=FeedbackPriority.LOW,
        )
    )
    item = render_quantity_feedback(diagnostic_set, catalog).items[0]
    assert item.text == "Contrôle interne personnalisé."
    assert item.audience is FeedbackAudience.TEACHER
    assert item.priority is FeedbackPriority.LOW
    assert item.diagnostic is diagnostic
    assert diagnostic_set.diagnostics[0] is diagnostic


def test_catalog_order_and_priority_do_not_reorder_diagnostics() -> None:
    diagnostic_set = _diagnostics("g=9")
    catalog = _catalog(
        _template(
            QuantityDiagnosticCode.UNCERTAINTY_MISSING,
            priority=FeedbackPriority.HIGH,
        ),
        _template(
            QuantityDiagnosticCode.UNIT_MISSING,
            priority=FeedbackPriority.LOW,
        ),
    )
    result = render_quantity_feedback(diagnostic_set, catalog)
    assert [item.code for item in result] == [
        QuantityDiagnosticCode.UNIT_MISSING,
        QuantityDiagnosticCode.UNCERTAINTY_MISSING,
    ]
    assert result.high_priority_items == (result.items[1],)


def test_feedback_set_converts_items_to_tuple() -> None:
    result = render_quantity_feedback(
        _diagnostics("g=9"), french_quantity_feedback_catalog()
    )
    rebuilt = QuantityFeedbackSet(
        result.diagnostic_set,
        result.catalog,
        list(result.items),  # type: ignore[arg-type]
    )
    assert isinstance(rebuilt.items, tuple)


@pytest.mark.parametrize("mutation", ["missing", "extra", "wrong", "order"])
def test_feedback_set_requires_exact_correspondence(mutation: str) -> None:
    result = render_quantity_feedback(
        _diagnostics("g=9"), french_quantity_feedback_catalog()
    )
    items = list(result.items)
    if mutation == "missing":
        items.pop()
    elif mutation == "extra":
        items.append(items[0])
    elif mutation == "wrong":
        foreign_template = replace(items[0].template, text="Autre formulation.")
        items[0] = replace(items[0], template=foreign_template)
    else:
        items.reverse()
    with pytest.raises(ValueError):
        QuantityFeedbackSet(
            result.diagnostic_set,
            result.catalog,
            items,  # type: ignore[arg-type]
        )


def test_feedback_set_rejects_equal_copy_of_source_diagnostic() -> None:
    result = render_quantity_feedback(
        _diagnostics("g=9 ± 1"), french_quantity_feedback_catalog()
    )
    copied = replace(result.items[0].diagnostic)
    item = replace(result.items[0], diagnostic=copied)
    with pytest.raises(ValueError):
        QuantityFeedbackSet(result.diagnostic_set, result.catalog, (item,))


def test_get_known_and_unknown_item() -> None:
    result = render_quantity_feedback(
        _diagnostics("g=9"), french_quantity_feedback_catalog()
    )
    assert result.get(QuantityDiagnosticCode.UNIT_MISSING) is result.items[0]
    assert result.get(QuantityDiagnosticCode.QUANTITY_MISSING) is None


def test_french_catalog_is_complete_exact_and_fresh() -> None:
    first = french_quantity_feedback_catalog()
    second = french_quantity_feedback_catalog()
    assert first == second
    assert first is not second
    assert first.templates is not second.templates
    assert all(a is not b for a, b in zip(first, second))
    assert first.id == "quantity-feedback-fr"
    assert first.title == "Feedback français pour les grandeurs numériques"
    assert first.language == "fr"
    assert [item.diagnostic_code for item in first] == list(QuantityDiagnosticCode)
    assert [item.audience for item in first] == [
        FeedbackAudience.STUDENT,
        FeedbackAudience.STUDENT,
        FeedbackAudience.STUDENT,
        FeedbackAudience.TEACHER,
        FeedbackAudience.STUDENT,
        FeedbackAudience.STUDENT,
        FeedbackAudience.STUDENT,
    ]
    assert [item.priority for item in first] == [
        FeedbackPriority.HIGH,
        FeedbackPriority.NORMAL,
        FeedbackPriority.HIGH,
        FeedbackPriority.NORMAL,
        FeedbackPriority.HIGH,
        FeedbackPriority.LOW,
        FeedbackPriority.LOW,
    ]


def test_renderer_class_and_function_are_deterministic_without_mutation() -> None:
    diagnostics = _diagnostics("g=9")
    catalog = french_quantity_feedback_catalog()
    before = (diagnostics, catalog)
    first = QuantityFeedbackRenderer().render(diagnostics, catalog)
    second = render_quantity_feedback(diagnostics, catalog)
    assert first == second
    assert before == (diagnostics, catalog)


def test_feedback_has_no_score_penalty_grade_or_ai_generated_text() -> None:
    item = render_quantity_feedback(
        _diagnostics("g=9"), french_quantity_feedback_catalog()
    ).items[0]
    assert not hasattr(item, "score")
    assert not hasattr(item, "penalty")
    assert not hasattr(item, "grade")
    assert not hasattr(item, "points")
    assert not hasattr(item, "generated_text")
