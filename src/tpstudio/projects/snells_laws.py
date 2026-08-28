"""Teacher configuration for the aligned Snell-Descartes notebook."""

from __future__ import annotations

from decimal import Decimal

from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    ComparisonInterpretationExpectationSet,
    ComparisonInterpretationKind,
    ComparisonJustificationElementKind,
    ComparisonJustificationExpectationSet,
    ComparisonJustificationRequirement,
    ComparisonPedagogicalContext,
    EvaluationBasis,
    ExpectedComparisonInterpretation,
    ExpectedComparisonJustification,
    ExpectedComparisonJustificationElement,
    ExpectedQuantity,
    ExpectedQuantityComparison,
    ExpectedRelation,
    ExpectedStudentNormalizedError,
    ExpectationSet,
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
    french_comparison_interpretation_feedback_catalog,
    french_comparison_justification_feedback_catalog,
    french_quantity_comparison_feedback_catalog,
    french_quantity_feedback_catalog,
)
from tpstudio.protocol import snells_laws_manipulations
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
    validate_teacher_project_configuration,
)


def _spec(identifier, label, kind, bases, depends_on=(), description=""):
    return ScientificProductionSpec(
        identifier, label, kind, bases, depends_on, True, description
    )


def _production_plan() -> ScientificProductionPlan:
    structural = EvaluationBasis.STRUCTURAL
    derived = EvaluationBasis.SUBMISSION_DERIVED
    declared = EvaluationBasis.DECLARED_CONTENT
    cross = EvaluationBasis.CROSS_PRODUCTION
    semantic = EvaluationBasis.SEMANTIC
    quantity = ScientificProductionKind.QUANTITY
    relation = ScientificProductionKind.RELATION
    interpretation = ScientificProductionKind.INTERPRETATION
    return ScientificProductionPlan(
        "snells-laws-productions",
        "Productions scientifiques — Lois de Snell-Descartes",
        (
            _spec("setup_understanding", "Compréhension du montage", interpretation, (semantic,)),
            _spec("critical_protocol", "Protocole de mesure de l'angle limite", interpretation, (semantic,)),
            _spec("critical_angle", "Angle limite", quantity, (structural, derived)),
            _spec("incidence_angle", "Angle d'incidence", quantity, (structural, derived)),
            _spec("refraction_angle", "Angle de réfraction", quantity, (structural, derived)),
            _spec("snell_relation", "Loi de Snell-Descartes", relation, (declared,)),
            _spec("direct_index_relation", "Indice par angle limite", relation, (declared,)),
            _spec("geometric_index_relation", "Indice par un couple d'angles", relation, (declared,)),
            _spec(
                "direct_index", "Indice — angle limite", quantity, (structural, derived),
                ("critical_angle", "direct_index_relation"),
            ),
            _spec(
                "direct_result_comment", "Commentaire du premier résultat",
                interpretation, (semantic,), ("direct_index",),
            ),
            _spec("single_pair_protocol", "Protocole avec un couple d'angles", interpretation, (semantic,)),
            _spec(
                "geometric_index", "Indice — couple d'angles", quantity,
                (structural, derived),
                ("incidence_angle", "refraction_angle", "geometric_index_relation"),
            ),
            _spec(
                "geometric_result_comment", "Commentaire du deuxième résultat",
                interpretation, (semantic,), ("geometric_index",),
            ),
            _spec("series_protocol", "Protocole de la série angulaire", interpretation, (semantic,)),
            _spec(
                "regression_graph", "Graphe de vérification de la réfraction",
                ScientificProductionKind.PLOT, (structural, derived),
                ("incidence_angle", "refraction_angle", "snell_relation"),
            ),
            _spec(
                "regression_slope", "Pente de la régression", quantity,
                (structural, derived), ("regression_graph",),
            ),
            _spec(
                "graph_analysis", "Analyse du graphe", interpretation,
                (semantic,), ("regression_graph", "regression_slope"),
            ),
            _spec(
                "slope_index_relation", "Relation entre pente et indice", relation,
                (declared,), ("regression_slope",),
            ),
            _spec(
                "regression_index", "Indice — série angulaire", quantity,
                (structural, derived),
                ("regression_graph", "regression_slope", "slope_index_relation"),
            ),
            _spec(
                "normalized_error_relation", "Formule de l'écart normalisé",
                relation, (declared,),
            ),
            _spec(
                "compare_direct_geometric", "Comparaison angle limite / couple",
                ScientificProductionKind.COMPARISON, (cross, semantic),
                ("direct_index", "geometric_index", "normalized_error_relation"),
            ),
            _spec(
                "compare_geometric_regression", "Comparaison couple / série",
                ScientificProductionKind.COMPARISON, (cross, semantic),
                ("geometric_index", "regression_index", "normalized_error_relation"),
            ),
            _spec(
                "final_conclusion", "Conclusion finale", interpretation,
                (semantic,), ("compare_direct_geometric", "compare_geometric_regression"),
            ),
            _spec(
                "method_limitations", "Limites de la méthode",
                ScientificProductionKind.JUSTIFICATION, (semantic,),
                ("final_conclusion",),
            ),
        ),
        "Plan limité aux productions effectivement présentes dans l'énoncé amélioré.",
    )


def _marker_binding(identifier, production_id, marker):
    return CellProductionBinding(
        identifier,
        production_id,
        NotebookCellSelector(NotebookCellSelectorKind.SOURCE_MARKER, marker),
        CellTextScope.full_source(),
        "Association littérale indépendante de l'indice de cellule.",
    )


def _binding_plan(plan: ScientificProductionPlan) -> NotebookBindingPlan:
    bindings = (
        _marker_binding("setup-response", "setup_understanding", "snell-setup-response"),
        _marker_binding("critical-protocol-response", "critical_protocol", "critical-protocol-response"),
        _marker_binding("critical-angle-cell", "critical_angle", "il= ? #degrés"),
        _marker_binding("incidence-angle-cell", "incidence_angle", "i1 = ?*np.pi/180"),
        _marker_binding("refraction-angle-cell", "refraction_angle", "i2 = ?*np.pi/180"),
        _marker_binding("snell-section", "snell_relation", "# Vérification de la loi de la réfraction"),
        _marker_binding("direct-relation-cell", "direct_index_relation", "n=1/np.sin(il)"),
        _marker_binding("geometric-relation-cell", "geometric_index_relation", "n=np.sin(i1)/np.sin(i2)"),
        _marker_binding("direct-index-cell", "direct_index", "### Résultat — Première méthode de mesure de l'indice"),
        _marker_binding("direct-comment-response", "direct_result_comment", "### Résultat — Première méthode de mesure de l'indice"),
        _marker_binding("single-pair-protocol-response", "single_pair_protocol", "single-pair-protocol-response"),
        _marker_binding("geometric-index-cell", "geometric_index", "### Résultat — Seconde méthode de mesure de l'indice"),
        _marker_binding("geometric-comment-response", "geometric_result_comment", "### Résultat — Seconde méthode de mesure de l'indice"),
        _marker_binding("series-protocol-response", "series_protocol", "series-protocol-response"),
        _marker_binding("regression-graph-cell", "regression_graph", "# Vérification graphique"),
        _marker_binding("regression-slope-cell", "regression_slope", "# Affichage de l'équation de la droite"),
        _marker_binding("graph-analysis-response", "graph_analysis", "graph-analysis-response"),
        _marker_binding("slope-index-cell", "slope_index_relation", "# Affichage de l'équation de la droite"),
        _marker_binding("regression-index-cell", "regression_index", "# Méthode statistique"),
        _marker_binding("normalized-error-cell", "normalized_error_relation", "En=abs(n.mean()-n0)"),
        _marker_binding("first-comparison-response", "compare_direct_geometric", "### Résultat — Seconde méthode de mesure de l'indice"),
        _marker_binding("second-comparison-response", "compare_geometric_regression", "### Comparaison des résultats obtenus"),
        _marker_binding("final-conclusion-response", "final_conclusion", "### Conclusion / bilan"),
        _marker_binding("method-limitations-response", "method_limitations", "### Conclusion / bilan"),
    )
    return NotebookBindingPlan(
        "snells-laws-bindings",
        "Associations du notebook aligné",
        plan,
        bindings,
        "Une absence ou une ambiguïté reste un échec explicite de résolution.",
    )


def _quantities(plan: ScientificProductionPlan) -> QuantityExpectationSet:
    required = PresenceRequirement.REQUIRED
    ignored = PresenceRequirement.IGNORE
    optional = PresenceRequirement.OPTIONAL
    return QuantityExpectationSet(
        plan,
        (
            # These are raw notebook inputs entered as paired variables
            # (for example il_deg and uil_deg), not reported results.  Their
            # presence is checked by execution; presentation requirements
            # apply to the derived indices below.
            ExpectedQuantity("critical_angle", "i_l", ("il", "il_deg"), "°", ("deg",), ignored, ignored),
            ExpectedQuantity("incidence_angle", "i_1", ("i1", "i1_deg"), "°", ("deg",), ignored, ignored),
            ExpectedQuantity("refraction_angle", "i_2", ("i2", "i2_deg"), "°", ("deg",), ignored, ignored),
            ExpectedQuantity("direct_index", "n_1", ("n", "n par angle limite"), None, (), ignored, required),
            ExpectedQuantity("geometric_index", "n_2", ("n", "n par un couple d'angles"), None, (), ignored, required),
            ExpectedQuantity("regression_slope", "a", ("pente",), None, (), ignored, ignored),
            ExpectedQuantity("regression_index", "n_3", ("n", "n moyen"), None, (), ignored, required),
        ),
    )


def _relations() -> ExpectationSet:
    return ExpectationSet(
        "snells-laws-relations",
        "Relations attendues — Lois de Snell-Descartes",
        relations=(
            ExpectedRelation("snell_relation", "Loi de Snell-Descartes", r"n_1 \sin(i_1) = n_2 \sin(i_2)", ("n1 sin(i1) = n2 sin(i2)",)),
            ExpectedRelation("direct_index_relation", "Indice par angle limite", r"n = 1 / \sin(i_l)", ("n=1/np.sin(il)",)),
            ExpectedRelation("geometric_index_relation", "Indice par couple", r"n = \sin(i_1) / \sin(i_2)", ("n=np.sin(i1)/np.sin(i2)",)),
            ExpectedRelation("slope_index_relation", "Pente et indice", "a = n", ("sin i_1 = a sin i_2 + b",)),
            ExpectedRelation("normalized_error_relation", "Écart normalisé", r"E_n = |n_a - n_b| / \sqrt{u(n_a)^2 + u(n_b)^2}", ("En=abs(n.mean()-n0)/np.sqrt(n.std(ddof=1)**2+un0**2)",)),
        ),
    )


def _uncertainties(quantities: QuantityExpectationSet):
    return UncertaintyQualityExpectationSet(
        quantities,
        tuple(
            UncertaintyQualitySpec(identifier)
            for identifier in (
                "direct_index", "geometric_index", "regression_index",
            )
        ),
    )


def _graphs(plan: ScientificProductionPlan) -> GraphExpectationSet:
    return GraphExpectationSet(
        plan,
        (
            GraphExpectation(
                "regression_graph",
                "sin(i2)",
                "sin(i1)",
                (r"$\sin i_2$", "sin(i2)"),
                (r"$\sin i_1$", "sin(i1)"),
                True,
                "regression_slope",
                "regression_index",
                "slope_index_relation",
                False,
                True,
                "L'abscisse est sin(i2), l'ordonnée sin(i1) et la pente représente n.",
                ExpectedGraphModel.LINEAR_THROUGH_ORIGIN,
            ),
        ),
    )


def _comparisons(plan, quantities):
    return QuantityComparisonExpectationSet(
        plan,
        quantities,
        (
            ExpectedQuantityComparison(
                "compare_direct_geometric", "direct_index", "geometric_index",
                pedagogical_context=ComparisonPedagogicalContext.OPEN,
                context_note="Comparer les deux premières déterminations sans imposer le résultat.",
            ),
            ExpectedQuantityComparison(
                "compare_geometric_regression", "geometric_index", "regression_index",
                pedagogical_context=ComparisonPedagogicalContext.INCOHERENCE_POSSIBLE,
                context_note="Une divergence est possible, sans annoncer une limitation comme résultat.",
            ),
        ),
    )


def _student_errors(comparisons):
    return StudentNormalizedErrorExpectationSet(
        comparisons,
        tuple(
            ExpectedStudentNormalizedError(
                item.production_id,
                ("E_n", "En"),
                Decimal("0.05"),
                "Tolérance de lecture correspondant à un En arrondi au centième.",
            )
            for item in comparisons
        ),
    )


_INTERPRETATION_PHRASES = (
    (ComparisonInterpretationKind.COHERENT, "Les mesures sont cohérentes"),
    (ComparisonInterpretationKind.COHERENT, "les résultats sont cohérents"),
    (ComparisonInterpretationKind.INCOHERENT, "Les mesures ne sont pas cohérentes"),
    (ComparisonInterpretationKind.INCOHERENT, "les résultats ne sont pas cohérents"),
    (ComparisonInterpretationKind.STRONGLY_INCOHERENT, "les résultats sont fortement incohérents"),
    (ComparisonInterpretationKind.METHOD_LIMITATION, "cette méthode est peu fiable"),
)


def _interpretations(comparisons):
    return ComparisonInterpretationExpectationSet(
        comparisons,
        tuple(
            ExpectedComparisonInterpretation(item.production_id, _INTERPRETATION_PHRASES)
            for item in comparisons
        ),
    )


def _justification(comparison_id: str, *, with_limitations: bool):
    required = ComparisonJustificationRequirement.REQUIRED
    optional = ComparisonJustificationRequirement.OPTIONAL
    elements = [
        ExpectedComparisonJustificationElement(
            "normalized_error_value", ComparisonJustificationElementKind.NORMALIZED_ERROR_VALUE,
            required, ("E_n =", "En ="),
        ),
        ExpectedComparisonJustificationElement(
            "threshold_reference", ComparisonJustificationElementKind.THRESHOLD_REFERENCE,
            required, (
                "En < 2", "E_n < 2", "inférieur à 2",
                "En >= 2", "E_n >= 2", "supérieur à 2",
                "En >= 4", "E_n >= 4", "supérieur à 4",
            ),
        ),
        ExpectedComparisonJustificationElement(
            "coherence_classification", ComparisonJustificationElementKind.COHERENCE_CLASSIFICATION,
            required, (
                "Les mesures sont cohérentes",
                "les résultats sont cohérents",
                "Les mesures ne sont pas cohérentes",
                "les mesures ne sont pas cohérentes",
                "les résultats ne sont pas cohérents",
                "les résultats sont fortement incohérents",
            ),
        ),
        ExpectedComparisonJustificationElement(
            "uncertainty_reference", ComparisonJustificationElementKind.UNCERTAINTY_REFERENCE,
            optional, ("avec leurs incertitudes",),
        ),
    ]
    if with_limitations:
        elements.extend((
            ExpectedComparisonJustificationElement(
                "method_limitation", ComparisonJustificationElementKind.METHOD_LIMITATION,
                optional, ("limites de la méthode",),
            ),
            ExpectedComparisonJustificationElement(
                "experimental_bias", ComparisonJustificationElementKind.EXPERIMENTAL_BIAS,
                optional, ("biais expérimental",),
            ),
            ExpectedComparisonJustificationElement(
                "measurement_limitation", ComparisonJustificationElementKind.MEASUREMENT_LIMITATION,
                optional, ("incertitude de lecture",),
            ),
        ))
    return ExpectedComparisonJustification(comparison_id, tuple(elements))


def _justifications(comparisons):
    return ComparisonJustificationExpectationSet(
        comparisons,
        (
            _justification("compare_direct_geometric", with_limitations=False),
            _justification("compare_geometric_regression", with_limitations=True),
        ),
    )


def _criterion(identifier, description, importance=SemanticCriterionImportance.REQUIRED):
    return SemanticCriterion(identifier, description, importance)


SEMANTIC_RESPONSE_EXPECTATIONS = (
    ExpectedSemanticResponse(
        "setup_understanding", SemanticRole.PROTOCOL,
        (
            _criterion("own_annotated_diagram", "Présenter le schéma personnel annoté du montage et des rayons utiles."),
            _criterion("center_normal_incidence", "Expliquer que le passage par le centre impose une incidence normale sur la face courbe."),
            _criterion("simplified_angle_reading", "Relier cette géométrie à l'absence de déviation sur la face courbe et à une lecture plus simple des angles."),
        ),
    ),
    ExpectedSemanticResponse(
        "critical_protocol", SemanticRole.PROTOCOL,
        (
            _criterion("critical_method_objective", "Identifier la détermination de l'indice à partir de l'angle limite comme objectif de la manipulation."),
            _criterion("identify_total_reflection_onset", "Décrire le repérage expérimental de l'apparition de la réflexion totale."),
            _criterion("measure_critical_angle", "Prévoir la mesure de l'angle limite sur le disque gradué."),
            _criterion("estimate_critical_uncertainty", "Justifier une incertitude-type tenant compte de la transition et de la lecture angulaire."),
        ),
    ),
    ExpectedSemanticResponse(
        "direct_result_comment", SemanticRole.INTERPRETATION,
        (
            _criterion("direct_result_with_uncertainty", "Donner l'indice obtenu par angle limite avec son incertitude et un arrondi cohérent."),
            _criterion("direct_precision_comment", "Commenter la précision et les difficultés expérimentales de la méthode."),
            _criterion("documented_value_comparison", "Discuter la cohérence avec une valeur documentée du Plexiglas.", SemanticCriterionImportance.RECOMMENDED),
        ),
    ),
    ExpectedSemanticResponse(
        "single_pair_protocol", SemanticRole.PROTOCOL,
        (
            _criterion("single_pair_objective", "Identifier la détermination de l'indice avec un couple d'angles et sa comparaison à la première méthode comme objectifs."),
            _criterion("measure_angle_pair", "Prévoir la mesure d'un couple angle d'incidence et angle de réfraction."),
            _criterion("justify_incidence_choice", "Justifier un angle d'incidence ni trop petit ni associé à une lecture ambiguë."),
            _criterion("justify_pair_uncertainties", "Justifier les incertitudes-types affectées aux deux angles."),
        ),
    ),
    ExpectedSemanticResponse(
        "geometric_result_comment", SemanticRole.INTERPRETATION,
        (
            _criterion("geometric_result_with_uncertainty", "Donner l'indice obtenu avec un couple d'angles et son incertitude."),
            _criterion("first_normalized_error", "Utiliser l'écart normalisé et le seuil 2 pour comparer les deux premières méthodes."),
            _criterion("plausible_difference_cause", "Proposer une cause expérimentale plausible en cas d'écart.", SemanticCriterionImportance.RECOMMENDED),
        ),
    ),
    ExpectedSemanticResponse(
        "series_protocol", SemanticRole.PROTOCOL,
        (
            _criterion("series_method_objective", "Identifier la vérification graphique de la loi et une nouvelle détermination de l'indice comme objectifs."),
            _criterion("at_least_fifteen_pairs", "Prévoir au moins quinze couples d'angles."),
            _criterion("span_useful_angle_range", "Répartir les mesures sur une plage angulaire exploitable."),
            _criterion("consistent_geometry_and_reading", "Conserver la géométrie et les conventions de lecture pendant la série."),
        ),
    ),
    ExpectedSemanticResponse(
        "graph_analysis", SemanticRole.INTERPRETATION,
        (
            _criterion("assess_point_alignment", "Examiner l'alignement des points expérimentaux."),
            _criterion("assess_zero_intercept", "Examiner si l'ordonnée à l'origine est compatible avec zéro."),
            _criterion("conclude_snell_verified", "Conclure sur la vérification de la loi dans le domaine étudié."),
            _criterion("interpret_slope_as_index", "Interpréter la pente comme l'indice du Plexiglas."),
        ),
    ),
    ExpectedSemanticResponse(
        "compare_geometric_regression", SemanticRole.INTERPRETATION,
        (
            _criterion("series_result_with_uncertainty", "Donner l'indice moyen de la série avec son incertitude."),
            _criterion("series_precision_comment", "Commenter la précision de cette détermination."),
            _criterion("second_normalized_error", "Utiliser l'écart normalisé et le seuil 2 pour comparer aux résultats précédents."),
        ),
    ),
    ExpectedSemanticResponse(
        "final_conclusion", SemanticRole.CONCLUSION,
        (
            _criterion("answer_both_objectives", "Répondre explicitement à la vérification de la loi et à la détermination de l'indice."),
            _criterion("summarize_results_and_choice", "Rappeler les résultats et justifier la valeur finalement retenue."),
            _criterion("limitations_and_improvement", "Présenter les principales limites expérimentales et une amélioration possible."),
        ),
    ),
)


def snells_laws_teacher_project() -> TeacherProjectConfiguration:
    """Build a fresh deterministic configuration without any file access."""

    plan = _production_plan()
    quantities = _quantities(plan)
    comparisons = _comparisons(plan, quantities)
    configuration = TeacherProjectConfiguration(
        TeacherProjectIdentity(
            "snells-laws-mvp", "Lois de Snell-Descartes", "Physique", "CPGE",
            "A79e1", "fr", "Configuration professeur du notebook aligné avec l'énoncé TeX.",
        ),
        (
            NotebookReference("statement", NotebookReferenceRole.STATEMENT, "Lois-de-Snell-Descartes.ipynb"),
            NotebookReference("correction", NotebookReferenceRole.CORRECTION, "Lois-de-Snell-Descartes-Corrige.ipynb"),
            NotebookReference("control-copy", NotebookReferenceRole.CONTROL_COPY, "Fausse-copie-etudiant-Lois-de-Snell-Descartes-ameliore.ipynb"),
        ),
        plan,
        _binding_plan(plan),
        quantities,
        _relations(),
        _uncertainties(quantities),
        _graphs(plan),
        comparisons,
        _student_errors(comparisons),
        _interpretations(comparisons),
        _justifications(comparisons),
        (
            french_quantity_feedback_catalog(),
            french_quantity_comparison_feedback_catalog(),
            french_comparison_interpretation_feedback_catalog(),
            french_comparison_justification_feedback_catalog(),
        ),
        "Configuration déclarative ; aucune copie, évaluation ou note n'est stockée.",
        experimental_manipulations=snells_laws_manipulations(),
        semantic_response_expectations=SEMANTIC_RESPONSE_EXPECTATIONS,
    )
    validate_teacher_project_configuration(configuration)
    return configuration
