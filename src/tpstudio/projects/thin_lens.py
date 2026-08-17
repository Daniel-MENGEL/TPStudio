"""Declarative teacher configuration for the thin-lens imaging TP."""

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
    ExpectedComparisonInterpretation,
    ExpectedComparisonJustification,
    ExpectedComparisonJustificationElement,
    ExpectedQuantity,
    ExpectedQuantityComparison,
    ExpectedRelation,
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
)
from tpstudio.feedback import (
    french_comparison_interpretation_feedback_catalog,
    french_comparison_justification_feedback_catalog,
    french_quantity_comparison_feedback_catalog,
    french_quantity_feedback_catalog,
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


def _plan() -> ScientificProductionPlan:
    structural = EvaluationBasis.STRUCTURAL
    declared = EvaluationBasis.DECLARED_CONTENT
    semantic = EvaluationBasis.SEMANTIC
    quantity = ScientificProductionKind.QUANTITY
    relation = ScientificProductionKind.RELATION
    plot = ScientificProductionKind.PLOT
    comparison = ScientificProductionKind.COMPARISON
    interpretation = ScientificProductionKind.INTERPRETATION
    justification = ScientificProductionKind.JUSTIFICATION
    return ScientificProductionPlan(
        "thin-lens-image-productions",
        "Productions scientifiques — Formation d'une image par une lentille mince",
        (
            ScientificProductionSpec("conjugation_relation", "Relation de conjugaison", relation, (declared,)),
            ScientificProductionSpec(
                "conjugation_graph", "Graphe de conjugaison", plot,
                (structural, declared), ("conjugation_relation",),
            ),
            ScientificProductionSpec(
                "conjugation_slope", "Pente de la régression", quantity,
                (structural,), ("conjugation_graph",),
            ),
            ScientificProductionSpec(
                "focal_intercept", "Ordonnée à l'origine", quantity,
                (structural,), ("conjugation_graph",),
            ),
            ScientificProductionSpec(
                "compare_conjugation", "Comparaison de la relation de conjugaison",
                comparison, (semantic,), ("conjugation_slope", "focal_intercept"),
            ),
            ScientificProductionSpec(
                "final_conclusion", "Conclusion finale", interpretation,
                (semantic,), ("compare_conjugation",),
            ),
            ScientificProductionSpec(
                "method_limitations", "Limites de la méthode", justification,
                (semantic,), ("final_conclusion",),
            ),
        ),
        "Contrat fondé sur 1/OA' - 1/OA = 1/f'.",
    )


def _bindings(plan: ScientificProductionPlan) -> NotebookBindingPlan:
    def marker(identifier: str, production_id: str, value: str) -> CellProductionBinding:
        return CellProductionBinding(
            identifier, production_id,
            NotebookCellSelector(NotebookCellSelectorKind.SOURCE_MARKER, value),
            CellTextScope.full_source(),
            "Association par marqueur source stable, indépendante de l'indice de cellule.",
        )

    return NotebookBindingPlan(
        "thin-lens-image-bindings",
        "Associations du TP lentille mince",
        plan,
        (
            marker("conjugation-graph-cell", "conjugation_graph", "plt.plot(invOA,invOAp"),
            marker("conjugation-slope-cell", "conjugation_slope", "np.polyfit(invOA,invOAp,1)"),
            marker("focal-intercept-cell", "focal_intercept", "np.polyfit(invOA,invOAp,1)"),
            marker("conjugation-relation-cell", "conjugation_relation", "1/OA' - 1/OA = 1/f'"),
            marker("conjugation-comparison-cell", "compare_conjugation", "distance focale"),
            marker("conclusion-cell", "final_conclusion", "Conclusion"),
            marker("limitations-cell", "method_limitations", "limites"),
        ),
        "Marqueurs dérivés des cellules du support Lentille réel.",
    )


def _quantities(plan: ScientificProductionPlan) -> QuantityExpectationSet:
    optional = PresenceRequirement.OPTIONAL
    return QuantityExpectationSet(
        plan,
        (
            ExpectedQuantity("conjugation_slope", "a", ("pente",), None, (), PresenceRequirement.IGNORE, optional),
            ExpectedQuantity("focal_intercept", "b", ("ordonnée à l'origine", "ordonnee a l origine"), None, (), PresenceRequirement.IGNORE, optional),
        ),
    )


def _relations() -> ExpectationSet:
    return ExpectationSet(
        "thin-lens-image-relations",
        "Relations attendues — Lentille mince",
        relations=(
            ExpectedRelation(
                "conjugation_relation",
                "Relation de conjugaison",
                "1/OA' - 1/OA = 1/f'",
                ("1/OA' = 1/OA + 1/f'",),
            ),
        ),
    )


def _graphs(plan: ScientificProductionPlan) -> GraphExpectationSet:
    return GraphExpectationSet(
        plan,
        (
            GraphExpectation(
                "conjugation_graph",
                "1/OA",
                "1/OA'",
                ("1/OA", "1/OA (inverse object distance)"),
                ("1/OA'", "1/OA' (inverse image distance)"),
                True,
                "conjugation_slope",
                None,
                "conjugation_relation",
                False,
                True,
                "Graphe de 1/OA' en fonction de 1/OA ; pente théorique 1 et intercept 1/f'.",
                ExpectedGraphModel.AFFINE,
            ),
        ),
    )


def thin_lens_teacher_project() -> TeacherProjectConfiguration:
    """Build the explicit, immutable Lentille teacher configuration."""
    plan = _plan()
    quantities = _quantities(plan)
    comparisons = QuantityComparisonExpectationSet(
        plan, quantities,
        (ExpectedQuantityComparison("compare_conjugation", "conjugation_slope", "focal_intercept"),),
    )
    interpretations = ComparisonInterpretationExpectationSet(
        comparisons,
        (ExpectedComparisonInterpretation(
            "compare_conjugation",
            ((ComparisonInterpretationKind.COHERENT, "Les mesures sont cohérentes"),
             (ComparisonInterpretationKind.INCOHERENT, "Les mesures ne sont pas cohérentes")),
        ),),
    )
    errors = StudentNormalizedErrorExpectationSet(
        comparisons,
        (ExpectedStudentNormalizedError("compare_conjugation", ("E_n", "En"), Decimal("0.05")),),
    )
    justifications = ComparisonJustificationExpectationSet(
        comparisons,
        (ExpectedComparisonJustification(
            "compare_conjugation",
            (ExpectedComparisonJustificationElement(
                "normalized_error_value", ComparisonJustificationElementKind.NORMALIZED_ERROR_VALUE,
                ComparisonJustificationRequirement.REQUIRED, ("E_n =", "En ="),
            ),),
        ),),
    )
    project = TeacherProjectConfiguration(
        TeacherProjectIdentity(
            "thin-lens-image",
            "Formation d'une image par une lentille mince",
            "Physique", "Lycée", "A74a6b", "fr",
            "Configuration déclarative du TP réel de lentille mince.",
        ),
        (
            NotebookReference("statement", NotebookReferenceRole.STATEMENT, "Formation-dune-image-par-une-lentille-mince.ipynb"),
            NotebookReference("correction", NotebookReferenceRole.CORRECTION, "Correction-Formation-dune-image-par-une-lentille-mince.ipynb"),
            NotebookReference("control-copy", NotebookReferenceRole.CONTROL_COPY, "TP_physique_2_Galaad-Louis_Louis[]Galaad.ipynb"),
        ),
        plan,
        _bindings(plan),
        quantities,
        _relations(),
        None,
        _graphs(plan),
        comparisons,
        errors,
        interpretations,
        justifications,
        (
            french_quantity_feedback_catalog(),
            french_quantity_comparison_feedback_catalog(),
            french_comparison_interpretation_feedback_catalog(),
            french_comparison_justification_feedback_catalog(),
        ),
        "Projet Lentille réel : y = 1/OA' et x = 1/OA, relation affine.",
    )
    validate_teacher_project_configuration(project)
    return project
