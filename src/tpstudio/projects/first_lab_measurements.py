"""Teacher contract for the guided ``Premières mesures au labo`` TP."""

from __future__ import annotations

from decimal import Decimal

from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    ComparisonInterpretationExpectationSet,
    ComparisonJustificationExpectationSet,
    ComparisonPedagogicalContext,
    ExpectedQuantity,
    ExpectedQuantityComparison,
    ExpectedStudentNormalizedError,
    ExpectationSet,
    EvaluationBasis,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
    PresenceRequirement,
    QuantityComparisonExpectationSet,
    QuantityExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
    StudentNormalizedErrorExpectationSet,
    UncertaintyQualityExpectationSet,
    UncertaintyQualitySpec,
)
from tpstudio.feedback import (
    french_quantity_comparison_feedback_catalog,
    french_quantity_feedback_catalog,
)
from tpstudio.semantic_analysis import (
    ExpectedSemanticResponse,
    SemanticCriterion,
    SemanticCriterionImportance,
    SemanticRole,
)

from .model import (
    ExpectedGraphModel,
    GraphExpectation,
    GraphExpectationSet,
    NotebookReference,
    NotebookReferenceRole,
    TeacherProjectConfiguration,
    TeacherProjectIdentity,
)


STATEMENT_FILENAME = "Premieres-mesures-au-labo.ipynb"
CORRECTION_FILENAME = "Premieres-mesures-au-labo-Corrige.ipynb"


def _criterion(
    criterion_id: str,
    description: str,
    importance: SemanticCriterionImportance = SemanticCriterionImportance.REQUIRED,
) -> SemanticCriterion:
    return SemanticCriterion(criterion_id, description, importance)


SEMANTIC_RESPONSE_EXPECTATIONS = (
    ExpectedSemanticResponse(
        "dynamic_objective",
        SemanticRole.OBJECTIVE,
        (
            _criterion(
                "determine_dynamic_stiffness",
                "Identifier que la manipulation vise à déterminer la raideur du ressort par une méthode dynamique.",
            ),
            _criterion(
                "measure_mass_and_period",
                "Identifier la masse suspendue et la période des oscillations comme grandeurs à mesurer.",
            ),
        ),
    ),
    ExpectedSemanticResponse(
        "dynamic_protocol",
        SemanticRole.PROTOCOL,
        (
            _criterion(
                "controlled_oscillations",
                "Prévoir de petites oscillations verticales, dans le domaine élastique, avec un lâcher maîtrisé.",
            ),
            _criterion(
                "multiple_periods_and_repetitions",
                "Chronométrer plusieurs périodes et répéter le mesurage afin d'observer la variabilité.",
            ),
            _criterion(
                "timing_reference_and_uncertainty",
                "Préciser un repère de déclenchement cohérent et les principales sources d'incertitude du chronométrage.",
                SemanticCriterionImportance.RECOMMENDED,
            ),
        ),
    ),
    ExpectedSemanticResponse(
        "period_result_comment",
        SemanticRole.INTERPRETATION,
        (
            _criterion(
                "period_with_uncertainty",
                "Donner la période du binôme avec son incertitude et son unité.",
            ),
            _criterion(
                "period_variability_comment",
                "Commenter la variabilité des répétitions sans comparer à une valeur universelle imposée.",
                SemanticCriterionImportance.RECOMMENDED,
            ),
        ),
    ),
    ExpectedSemanticResponse(
        "period_neighbor_comparison",
        SemanticRole.INTERPRETATION,
        (
            _criterion(
                "cite_both_period_results",
                "Rappeler les périodes des deux binômes avec leurs incertitudes et leurs unités.",
            ),
            _criterion(
                "period_normalized_error_classification",
                "Utiliser l'écart normalisé et le seuil 2 pour conclure sur la compatibilité des périodes.",
            ),
            _criterion(
                "different_springs_context",
                "Expliquer qu'une incompatibilité peut être légitime lorsque les binômes étudient des ressorts différents.",
            ),
        ),
    ),
    ExpectedSemanticResponse(
        "dynamic_stiffness_interpretation",
        SemanticRole.INTERPRETATION,
        (
            _criterion(
                "dynamic_stiffness_with_uncertainty",
                "Donner la raideur dynamique avec son incertitude et son unité.",
            ),
            _criterion(
                "dynamic_uncertainty_sources",
                "Relier l'incertitude obtenue aux incertitudes sur la masse et le chronométrage.",
            ),
            _criterion(
                "student_system_interpretation",
                "Interpréter le résultat pour le ressort réellement étudié par le binôme, sans valeur attendue imposée.",
                SemanticCriterionImportance.RECOMMENDED,
            ),
        ),
    ),
    ExpectedSemanticResponse(
        "hooke_objective",
        SemanticRole.OBJECTIVE,
        (
            _criterion(
                "test_hooke_affine_model",
                "Identifier que l'étude statique vise à tester le caractère affine de la longueur en fonction de la masse.",
            ),
            _criterion(
                "infer_stiffness_from_slope",
                "Prévoir de déduire la raideur de la pente à l'aide de la relation a = g/k.",
            ),
        ),
    ),
    ExpectedSemanticResponse(
        "hooke_protocol",
        SemanticRole.PROTOCOL,
        (
            _criterion(
                "several_masses_equilibrium_lengths",
                "Mesurer les longueurs d'équilibre pour plusieurs masses avec un même repère.",
            ),
            _criterion(
                "reading_precautions",
                "Mentionner des précautions de lecture et le maintien dans le domaine élastique.",
            ),
            _criterion(
                "mass_length_uncertainties",
                "Identifier les incertitudes associées aux mesures de masse et de longueur.",
                SemanticCriterionImportance.RECOMMENDED,
            ),
        ),
    ),
    ExpectedSemanticResponse(
        "hooke_law_validation",
        SemanticRole.INTERPRETATION,
        (
            _criterion(
                "points_aligned_with_uncertainties",
                "Constater que les points expérimentaux sont alignés, compte tenu de leurs incertitudes.",
            ),
            _criterion(
                "hooke_law_verified_in_studied_range",
                "Conclure que la loi de Hooke est vérifiée dans le domaine étudié.",
            ),
        ),
    ),
    ExpectedSemanticResponse(
        "hooke_interpretation",
        SemanticRole.INTERPRETATION,
        (
            _criterion(
                "slope_and_intercept_meaning",
                "Interpréter la pente a = g/k et l'ordonnée à l'origine comme la longueur à vide.",
            ),
            _criterion(
                "static_stiffness_with_uncertainty",
                "Donner la raideur statique avec son incertitude et son unité.",
            ),
        ),
    ),
    ExpectedSemanticResponse(
        "stiffness_comparison_interpretation",
        SemanticRole.INTERPRETATION,
        (
            _criterion(
                "cite_both_stiffness_results",
                "Rappeler les deux valeurs de raideur avec leurs incertitudes.",
            ),
            _criterion(
                "normalized_error_classification",
                "Utiliser l'écart normalisé et le seuil 2 pour conclure sur la compatibilité.",
            ),
            _criterion(
                "experimental_causes",
                "Discuter des causes expérimentales plausibles si un écart doit être expliqué.",
                SemanticCriterionImportance.RECOMMENDED,
            ),
        ),
    ),
    ExpectedSemanticResponse(
        "final_conclusion",
        SemanticRole.CONCLUSION,
        (
            _criterion(
                "two_methods_and_results",
                "Présenter les deux méthodes et leurs résultats avec incertitudes.",
            ),
            _criterion(
                "hooke_and_quantitative_comparison",
                "Conclure sur la loi de Hooke et sur la comparaison quantitative des deux raideurs.",
            ),
            _criterion(
                "limitations_and_learning",
                "Mentionner les principales limites expérimentales et un apprentissage relatif aux incertitudes ou au rapport.",
                SemanticCriterionImportance.RECOMMENDED,
            ),
        ),
    ),
)


def _plan() -> ScientificProductionPlan:
    structural = EvaluationBasis.STRUCTURAL
    semantic = EvaluationBasis.SEMANTIC
    quantity = ScientificProductionKind.QUANTITY
    interpretation = ScientificProductionKind.INTERPRETATION
    return ScientificProductionPlan(
        "first-lab-measurements-productions",
        "Productions scientifiques — Premières mesures au labo",
        (
            ScientificProductionSpec("dynamic_objective", "Objectif de la méthode dynamique", interpretation, (semantic,)),
            ScientificProductionSpec("dynamic_protocol", "Protocole de la méthode dynamique", interpretation, (semantic,)),
            ScientificProductionSpec("period_result", "Période mesurée", quantity, (structural,)),
            ScientificProductionSpec("period_result_comment", "Interprétation de la période", interpretation, (semantic,), ("period_result",)),
            ScientificProductionSpec("period_neighbor_comparison", "Comparaison de la période avec le groupe voisin", interpretation, (semantic,), ("period_result",)),
            ScientificProductionSpec("dynamic_stiffness", "Raideur dynamique", quantity, (structural,)),
            ScientificProductionSpec("dynamic_stiffness_interpretation", "Interprétation de la raideur dynamique", interpretation, (semantic,), ("dynamic_stiffness",)),
            ScientificProductionSpec("hooke_objective", "Objectif de l'étude statique", interpretation, (semantic,)),
            ScientificProductionSpec("hooke_protocol", "Protocole de l'étude statique", interpretation, (semantic,)),
            ScientificProductionSpec("hooke_graph", "Graphe statique de la loi de Hooke", ScientificProductionKind.PLOT, (structural,)),
            ScientificProductionSpec("hooke_law_validation", "Conclusion sur la vérification de la loi de Hooke", interpretation, (semantic,), ("hooke_graph",)),
            ScientificProductionSpec("hooke_slope", "Pente de l'ajustement affine", quantity, (structural,)),
            ScientificProductionSpec("static_stiffness", "Raideur statique", quantity, (structural,)),
            ScientificProductionSpec("hooke_interpretation", "Détermination statique de la raideur", interpretation, (semantic,), ("hooke_law_validation", "static_stiffness")),
            ScientificProductionSpec("stiffness_comparison", "Comparaison des deux raideurs", ScientificProductionKind.COMPARISON, (structural,), ("dynamic_stiffness", "static_stiffness")),
            ScientificProductionSpec("stiffness_comparison_interpretation", "Interprétation de la comparaison", interpretation, (semantic,), ("stiffness_comparison",)),
            ScientificProductionSpec("final_conclusion", "Conclusion générale", interpretation, (semantic,), ("stiffness_comparison_interpretation",)),
        ),
        "Contrat adapté à un TP guidé utilisant le ressort propre à chaque binôme.",
    )


def _marker(identifier: str, production_id: str, marker: str) -> CellProductionBinding:
    return CellProductionBinding(
        identifier,
        production_id,
        NotebookCellSelector(NotebookCellSelectorKind.SOURCE_MARKER, marker),
        CellTextScope.full_source(),
        "Association par marqueur source stable du notebook aligné.",
    )


def _bindings(plan: ScientificProductionPlan) -> NotebookBindingPlan:
    bindings = (
        _marker("period-result-cell", "period_result", "T_mean = T_values.mean()"),
        _marker("dynamic-stiffness-cell", "dynamic_stiffness", "k_dyn = k_dyn_samples.mean()"),
        _marker("hooke-graph-cell", "hooke_graph", 'plt.title("Vérification statique de la loi de Hooke")'),
        _marker("hooke-slope-cell", "hooke_slope", "a_fit, l0_fit = np.polyfit(m_static, l_static, 1)"),
        _marker("static-stiffness-cell", "static_stiffness", "k_static = k_static_samples.mean()"),
        _marker("stiffness-comparison-cell", "stiffness_comparison", "E_N = abs(k_dyn - k_static)"),
        *(
            _marker(
                f"{contract.production_id.replace('_', '-')}-response",
                contract.production_id,
                marker,
            )
            for contract, marker in zip(
                SEMANTIC_RESPONSE_EXPECTATIONS,
                (
                    "dynamic-objective-response",
                    "dynamic-protocol-response",
                    "period-result-response",
                    "period-neighbor-comparison-response",
                    "dynamic-stiffness-interpretation-response",
                    "hooke-objective-response",
                    "hooke-protocol-response",
                    "hooke-law-validation-response",
                    "hooke-interpretation-response",
                    "stiffness-comparison-response",
                    "final-conclusion-response",
                ),
                strict=True,
            )
        ),
    )
    return NotebookBindingPlan(
        "first-lab-measurements-bindings",
        "Associations du TP Premières mesures au labo",
        plan,
        bindings,
        "Le schéma photographié reste soumis à l'examen visuel du professeur.",
    )


def first_lab_measurements_teacher_project() -> TeacherProjectConfiguration:
    plan = _plan()
    required = PresenceRequirement.REQUIRED
    ignored = PresenceRequirement.IGNORE
    quantities = QuantityExpectationSet(
        plan,
        (
            ExpectedQuantity("period_result", "T", ("T_mean",), "s", (), required, PresenceRequirement.OPTIONAL, ignored, "Période moyenne du ressort du binôme."),
            ExpectedQuantity("dynamic_stiffness", "k_dyn", ("k_dynamique", "k dynamique"), "N/m", ("N.m^-1", "N·m^-1"), required, required, ignored, "Raideur obtenue par la méthode dynamique."),
            ExpectedQuantity("hooke_slope", "a_fit", ("a",), "m/kg", ("m.kg^-1", "m·kg^-1"), required, ignored, ignored, "Pente de l'ajustement affine l(m)."),
            ExpectedQuantity("static_stiffness", "k_static", ("k_statique", "k statique"), "N/m", ("N.m^-1", "N·m^-1"), required, required, ignored, "Raideur obtenue par la méthode statique."),
        ),
    )
    uncertainties = UncertaintyQualityExpectationSet(
        quantities,
        tuple(UncertaintyQualitySpec(identifier) for identifier in ("period_result", "dynamic_stiffness", "static_stiffness")),
    )
    graphs = GraphExpectationSet(
        plan,
        (
            GraphExpectation(
                "hooke_graph",
                "m_static",
                "l_static",
                ("Masse suspendue m (kg)", "m_static"),
                ("Longueur du ressort l (m)", "l_static"),
                False,
                "hooke_slope",
                None,
                None,
                True,
                True,
                "Longueur d'équilibre en fonction de la masse, avec incertitudes et ajustement affine.",
                ExpectedGraphModel.AFFINE,
            ),
        ),
    )
    comparisons = QuantityComparisonExpectationSet(
        plan,
        quantities,
        (
            ExpectedQuantityComparison(
                "stiffness_comparison",
                "dynamic_stiffness",
                "static_stiffness",
                pedagogical_context=ComparisonPedagogicalContext.OPEN,
                context_note="La compatibilité dépend des mesures du binôme et n'est pas imposée à l'avance.",
            ),
        ),
    )
    student_errors = StudentNormalizedErrorExpectationSet(
        comparisons,
        (
            ExpectedStudentNormalizedError(
                "stiffness_comparison",
                ("E_N", "E_n", "En", "Écart normalisé"),
                Decimal("0.01"),
                "Écart normalisé calculé à partir des deux raideurs et de leurs incertitudes.",
            ),
        ),
    )
    return TeacherProjectConfiguration(
        TeacherProjectIdentity(
            "first-lab-measurements",
            "Premières mesures au labo",
            "Physique",
            "Lycée",
            "A79d8",
            "fr",
            "TP-cours guidé sur les incertitudes, la loi de Hooke et la rédaction scientifique.",
        ),
        (
            NotebookReference("statement", NotebookReferenceRole.STATEMENT, STATEMENT_FILENAME),
            NotebookReference("correction", NotebookReferenceRole.CORRECTION, CORRECTION_FILENAME),
        ),
        plan,
        _bindings(plan),
        quantities,
        ExpectationSet("first-lab-measurements-relations", "Relations attendues — Premières mesures", relations=()),
        uncertainties,
        graphs,
        comparisons,
        student_errors,
        ComparisonInterpretationExpectationSet(comparisons, ()),
        ComparisonJustificationExpectationSet(comparisons, ()),
        (french_quantity_feedback_catalog(), french_quantity_comparison_feedback_catalog()),
        "Analyse des résultats propres au binôme ; aucune valeur numérique du corrigé n'est une cible.",
        semantic_response_expectations=SEMANTIC_RESPONSE_EXPECTATIONS,
    )
