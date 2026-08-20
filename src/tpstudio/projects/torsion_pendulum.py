"""Structural teacher configuration for the torsion-pendulum notebook.

This first milestone deliberately declares only the project identity, production
plan and stable notebook bindings.  Scientific graph, uncertainty and derived
calculation expectations are intentionally left for later milestones.
"""

from __future__ import annotations

from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    ComparisonInterpretationExpectationSet,
    ComparisonJustificationExpectationSet,
    ExpectationSet,
    EvaluationBasis,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
    QuantityComparisonExpectationSet,
    QuantityExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
    StudentNormalizedErrorExpectationSet,
)
from tpstudio.protocol import ExperimentalManipulation

from .model import (
    NotebookReference,
    NotebookReferenceRole,
    TeacherProjectConfiguration,
    TeacherProjectIdentity,
    validate_teacher_project_configuration,
)


_NOTEBOOK_CELL_IDS = {
    "dynamic_protocol": "331016c9",
    "dynamic_interpretation": "7b0bcc33",
    "static_protocol": "e3b91c37",
    "static_interpretation": "b87aaac0",
    "comparison": "354b8f1d",
    "conclusion": "8b0b1f2e",
}


def _plan() -> ScientificProductionPlan:
    structural = EvaluationBasis.STRUCTURAL
    declared = EvaluationBasis.DECLARED_CONTENT
    semantic = EvaluationBasis.SEMANTIC
    quantity = ScientificProductionKind.QUANTITY
    relation = ScientificProductionKind.RELATION
    plot = ScientificProductionKind.PLOT
    comparison = ScientificProductionKind.COMPARISON
    interpretation = ScientificProductionKind.INTERPRETATION
    return ScientificProductionPlan(
        "torsion-pendulum-productions",
        "Productions scientifiques — Pendule de torsion",
        (
            ScientificProductionSpec("dynamic_mass", "Masse moyenne dynamique", quantity, (structural,)),
            ScientificProductionSpec("dynamic_thickness", "Épaisseur moyenne dynamique", quantity, (structural,)),
            ScientificProductionSpec("dynamic_periods", "Périodes propres", quantity, (structural,)),
            ScientificProductionSpec(
                "dynamic_graph", "Graphe dynamique", plot, (structural, declared),
                ("dynamic_periods",),
            ),
            ScientificProductionSpec(
                "dynamic_torsion_constant", "Constante de torsion dynamique", quantity,
                (structural,), ("dynamic_graph", "dynamic_mass"),
            ),
            ScientificProductionSpec(
                "bar_inertia", "Moment d'inertie de la barre", quantity,
                (structural,), ("dynamic_graph", "dynamic_torsion_constant"),
            ),
            ScientificProductionSpec(
                "dynamic_model_relation", "Relation du modèle dynamique", relation,
                (declared,), ("dynamic_graph",),
            ),
            ScientificProductionSpec(
                "dynamic_interpretation", "Interprétation de l'étude dynamique",
                interpretation, (semantic,),
                ("dynamic_graph", "dynamic_torsion_constant", "bar_inertia"),
            ),
            ScientificProductionSpec("static_mass", "Masse suspendue", quantity, (structural,)),
            ScientificProductionSpec("static_reference_angle", "Angle de référence", quantity, (structural,)),
            ScientificProductionSpec("static_distances", "Distances statiques", quantity, (structural,)),
            ScientificProductionSpec("static_equilibrium_angles", "Angles d'équilibre", quantity, (structural,)),
            ScientificProductionSpec(
                "static_torsion_constant", "Constante de torsion statique", quantity,
                (structural,), ("static_mass", "static_distances", "static_equilibrium_angles"),
            ),
            ScientificProductionSpec(
                "static_model_relation", "Relation du modèle statique", relation,
                (declared,), ("static_torsion_constant",),
            ),
            ScientificProductionSpec(
                "static_interpretation", "Interprétation de l'étude statique",
                interpretation, (semantic,), ("static_torsion_constant",),
            ),
            ScientificProductionSpec(
                "dynamic_static_comparison", "Comparaison des deux méthodes",
                comparison, (semantic,),
                ("dynamic_torsion_constant", "static_torsion_constant"),
            ),
            ScientificProductionSpec(
                "normalized_error_relation", "Écart normalisé", relation,
                (declared,), ("dynamic_static_comparison",),
            ),
            ScientificProductionSpec(
                "general_conclusion", "Conclusion générale", interpretation,
                (semantic,), ("dynamic_static_comparison",),
            ),
        ),
        "Socle structurel A76e2a ; les attentes scientifiques avancées restent à définir.",
    )


def _cell(identifier: str, production_id: str, cell_id: str) -> CellProductionBinding:
    return CellProductionBinding(
        identifier,
        production_id,
        NotebookCellSelector(NotebookCellSelectorKind.CELL_ID, cell_id),
        CellTextScope.full_source(),
        "Binding fondé sur l'identifiant stable de cellule du notebook harmonisé.",
    )


def _marker(identifier: str, production_id: str, marker: str) -> CellProductionBinding:
    return CellProductionBinding(
        identifier,
        production_id,
        NotebookCellSelector(NotebookCellSelectorKind.SOURCE_MARKER, marker),
        CellTextScope.full_source(),
        "Binding structurel par marqueur source stable.",
    )


def _bindings(plan: ScientificProductionPlan) -> NotebookBindingPlan:
    bindings = (
        _marker("dynamic-mass-cell", "dynamic_mass", "m = ?"),
        _marker("dynamic-thickness-cell", "dynamic_thickness", "L = ?"),
        _marker("dynamic-periods-cell", "dynamic_periods", "T_0 ="),
        _marker("dynamic-graph-cell", "dynamic_graph", "plt.plot(?, ?,"),
        _marker("dynamic-model-cell", "dynamic_model_relation", "np.polyfit"),
        _marker("dynamic-c-cell", "dynamic_torsion_constant", "C = 8*np.pi**2*m/a"),
        _marker("dynamic-inertia-cell", "bar_inertia", "J_b = ?"),
        _cell("dynamic-interpretation-cell", "dynamic_interpretation", _NOTEBOOK_CELL_IDS["dynamic_interpretation"]),
        _marker("static-mass-cell", "static_mass", "m_susp = ?"),
        _marker("static-reference-angle-cell", "static_reference_angle", "theta_0 = ?"),
        _marker("static-distance-cell", "static_distances", "d = np.array"),
        _marker("static-equilibrium-angle-cell", "static_equilibrium_angles", "theta_eq = np.array"),
        _marker("static-c-cell", "static_torsion_constant", "C2 = ?"),
        _marker("static-model-cell", "static_model_relation", "C2 = ?"),
        _cell("static-interpretation-cell", "static_interpretation", _NOTEBOOK_CELL_IDS["static_interpretation"]),
        _cell("comparison-cell", "dynamic_static_comparison", _NOTEBOOK_CELL_IDS["comparison"]),
        _marker("normalized-error-cell", "normalized_error_relation", "E_n = ?"),
        _cell("conclusion-cell", "general_conclusion", _NOTEBOOK_CELL_IDS["conclusion"]),
    )
    return NotebookBindingPlan(
        "torsion-pendulum-bindings",
        "Associations du notebook Pendule de torsion",
        plan,
        bindings,
        "Bindings A76e2a ; les marqueurs et identifiants sont propres au support, pas au moteur.",
    )


def _empty_expectations(plan: ScientificProductionPlan):
    quantities = QuantityExpectationSet(plan, ())
    relations = ExpectationSet(
        "torsion-pendulum-relations",
        "Relations déclarées — Pendule de torsion",
        relations=(),
    )
    comparisons = QuantityComparisonExpectationSet(plan, quantities, ())
    student_errors = StudentNormalizedErrorExpectationSet(comparisons, ())
    interpretations = ComparisonInterpretationExpectationSet(comparisons, ())
    justifications = ComparisonJustificationExpectationSet(comparisons, ())
    return quantities, relations, comparisons, student_errors, interpretations, justifications


def torsion_pendulum_teacher_project() -> TeacherProjectConfiguration:
    """Build the structural A76e2a configuration for the torsion pendulum."""
    plan = _plan()
    quantities, relations, comparisons, student_errors, interpretations, justifications = _empty_expectations(plan)
    configuration = TeacherProjectConfiguration(
        TeacherProjectIdentity(
            "torsion-pendulum",
            "Pendule de torsion",
            "Physique",
            "Lycée",
            "A76e2a",
            "fr",
            "Socle structurel du contrat professeur Pendule de torsion.",
        ),
        (
            NotebookReference(
                "statement", NotebookReferenceRole.STATEMENT,
                "Pendule-de-torsion-TPStudio-v2-ajuste-v2.ipynb",
            ),
        ),
        plan,
        _bindings(plan),
        quantities,
        relations,
        None,
        None,
        comparisons,
        student_errors,
        interpretations,
        justifications,
        (),
        "A76e2a : identité, productions et bindings ; pas de moteur scientifique Pendule.",
        experimental_manipulations=(
            ExperimentalManipulation("dynamic-study", "Étude dynamique", "1. Étude dynamique"),
            ExperimentalManipulation("static-study", "Étude statique", "2. Étude statique"),
        ),
    )
    validate_teacher_project_configuration(configuration)
    return configuration
