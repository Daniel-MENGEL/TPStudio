"""Structural teacher configuration for the torsion-pendulum notebook.

The project keeps its derived calculation expectation declarative; execution
remains outside the configuration/readiness path.
"""

from __future__ import annotations

from decimal import Decimal

from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    ComparisonInterpretationExpectationSet,
    ComparisonJustificationExpectationSet,
    DerivedQuantityExpectationSet,
    Divide,
    ExpectationSet,
    EvaluationBasis,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
    NotebookValueTransform,
    ExpectedDerivedQuantity,
    ExpectedQuantity,
    ExpectedQuantitySeries,
    Multiply,
    OperandRef,
    ProductionValue,
    QuantityComparisonExpectationSet,
    QuantityExpectationSet,
    QuantitySeriesExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
    StudentNormalizedErrorExpectationSet,
    RegressionParameter,
    RegressionParameterKind,
    TeacherConstant,
)
from tpstudio.protocol import ExperimentalManipulation

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
                "static_interpretation", "Interprétation de l'étude statique",
                interpretation, (semantic,), ("static_torsion_constant",),
            ),
            ScientificProductionSpec(
                "dynamic_static_comparison", "Comparaison des deux méthodes",
                comparison, (semantic,),
                ("dynamic_torsion_constant", "static_torsion_constant"),
            ),
            ScientificProductionSpec(
                "normalized_error", "Écart normalisé", quantity,
                (structural,), ("dynamic_static_comparison",),
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


def _marker(
    identifier: str,
    production_id: str,
    marker: str,
    *,
    value_transform: NotebookValueTransform = NotebookValueTransform.IDENTITY,
) -> CellProductionBinding:
    return CellProductionBinding(
        identifier,
        production_id,
        NotebookCellSelector(NotebookCellSelectorKind.SOURCE_MARKER, marker),
        CellTextScope.full_source(),
        "Binding structurel par marqueur source stable.",
        value_transform,
    )


def _bindings(plan: ScientificProductionPlan) -> NotebookBindingPlan:
    bindings = (
        _marker("dynamic-mass-cell", "dynamic_mass", "m = ?"),
        _marker(
            "dynamic-thickness-cell", "dynamic_thickness", "L = ?",
            value_transform=NotebookValueTransform.MEAN,
        ),
        _marker("dynamic-periods-cell", "dynamic_periods", "T_0 ="),
        _marker("dynamic-graph-cell", "dynamic_graph", "plt.plot(?, ?,"),
        _marker("dynamic-regression-cell", "dynamic_graph", "np.polyfit"),
        _marker("dynamic-c-cell", "dynamic_torsion_constant", "C = 8*np.pi**2*m/a"),
        _marker("dynamic-inertia-cell", "bar_inertia", "J_b = ?"),
        _cell("dynamic-interpretation-cell", "dynamic_interpretation", _NOTEBOOK_CELL_IDS["dynamic_interpretation"]),
        _marker("static-mass-cell", "static_mass", "m_susp = ?"),
        _marker("static-reference-angle-cell", "static_reference_angle", "theta_0 = ?"),
        _marker("static-distance-cell", "static_distances", "d = np.array"),
        _marker("static-equilibrium-angle-cell", "static_equilibrium_angles", "theta_eq = np.array"),
        _marker("static-c-cell", "static_torsion_constant", "C2 = ?"),
        _cell("static-interpretation-cell", "static_interpretation", _NOTEBOOK_CELL_IDS["static_interpretation"]),
        _cell("comparison-cell", "dynamic_static_comparison", _NOTEBOOK_CELL_IDS["comparison"]),
        _marker("normalized-error-cell", "normalized_error", "E_n = ?"),
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
    quantities = QuantityExpectationSet(
        plan,
        (
            ExpectedQuantity(
                production_id="dynamic_mass",
                canonical_symbol="m",
                canonical_unit="kg",
                description="Masse moyenne des masses hexagonales, exprimée en kilogrammes.",
            ),
            ExpectedQuantity(
                production_id="dynamic_thickness",
                canonical_symbol="L",
                canonical_unit="m",
                description="Épaisseur moyenne des masses hexagonales, exprimée en mètres.",
            ),
        ),
    )
    relations = ExpectationSet(
        "torsion-pendulum-relations",
        "Relations déclarées — Pendule de torsion",
        relations=(),
    )
    comparisons = QuantityComparisonExpectationSet(plan, quantities, ())
    student_errors = StudentNormalizedErrorExpectationSet(comparisons, ())
    interpretations = ComparisonInterpretationExpectationSet(comparisons, ())
    justifications = ComparisonJustificationExpectationSet(comparisons, ())
    graphs = GraphExpectationSet(
        plan,
        (
            GraphExpectation(
                production_id="dynamic_graph",
                x_expression="(r + L.mean()/2)**2",
                y_expression="T_0**2",
                accepted_x_labels=("(r+L/2)^2 en m^2", "(r + L/2)^2"),
                accepted_y_labels=("T_0^2 en s^2", "T_0^2"),
                regression_required=True,
                slope_quantity_id=None,
                index_quantity_id=None,
                slope_index_relation_id=None,
                description="Graphe affine de T_0^2 en fonction de (r+L/2)^2.",
                expected_model=ExpectedGraphModel.AFFINE,
            ),
        ),
    )
    return quantities, relations, graphs, comparisons, student_errors, interpretations, justifications


def torsion_pendulum_teacher_project() -> TeacherProjectConfiguration:
    """Build the structural A76e2a configuration for the torsion pendulum."""
    plan = _plan()
    quantities, relations, graphs, comparisons, student_errors, interpretations, justifications = _empty_expectations(plan)
    slope = RegressionParameter("dynamic_graph", RegressionParameterKind.SLOPE)
    intercept = RegressionParameter("dynamic_graph", RegressionParameterKind.INTERCEPT)
    dynamic_mass = ProductionValue("dynamic_mass")
    dynamic_constant = ProductionValue("dynamic_torsion_constant")
    eight_pi_squared = TeacherConstant(
        "eight_pi_squared", Decimal("78.9568352087148689506759279990")
    )
    four_pi_squared = TeacherConstant(
        "four_pi_squared", Decimal("39.4784176043574344753379639995")
    )
    derived_expectations = DerivedQuantityExpectationSet((
        ExpectedDerivedQuantity(
            production_id="dynamic_torsion_constant",
            canonical_symbol="C",
            sources=(dynamic_mass, slope, eight_pi_squared),
            rule=Divide(
                Multiply(OperandRef(eight_pi_squared), OperandRef(dynamic_mass)),
                OperandRef(slope),
            ),
            description="Constante de torsion dynamique déduite de la pente et de m.",
        ),
        ExpectedDerivedQuantity(
            production_id="bar_inertia",
            canonical_symbol="J_b",
            sources=(intercept, dynamic_constant, four_pi_squared),
            rule=Divide(
                Multiply(OperandRef(intercept), OperandRef(dynamic_constant)),
                OperandRef(four_pi_squared),
            ),
            description=(
                "Moment d'inertie de la barre déduit de l'ordonnée à l'origine "
                "de la régression dynamique."
            ),
        ),
    ))
    series_expectations = QuantitySeriesExpectationSet(
        plan,
        (ExpectedQuantitySeries(
            production_id="dynamic_periods",
            canonical_symbol="T_0",
            canonical_unit="s",
            expected_length=8,
            description="Huit périodes propres mesurées pour les huit valeurs de r.",
        ),),
    )
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
        graphs,
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
        derived_quantity_expectation_set=derived_expectations,
        quantity_series_expectation_set=series_expectations,
    )
    validate_teacher_project_configuration(configuration)
    return configuration
