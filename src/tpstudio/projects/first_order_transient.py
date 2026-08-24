"""Minimal teacher contract for the first-order transient-response TP."""

from __future__ import annotations

from tpstudio.expectations import (
    CellProductionBinding, CellTextScope, ComparisonInterpretationExpectationSet,
    ComparisonJustificationExpectationSet, ExpectationSet, EvaluationBasis,
    NotebookBindingPlan, NotebookCellSelector, NotebookCellSelectorKind,
    QuantityComparisonExpectationSet, QuantityExpectationSet,
    ScientificProductionKind, ScientificProductionPlan, ScientificProductionSpec,
    StudentNormalizedErrorExpectationSet,
)
from .model import (
    GraphExpectation, GraphExpectationSet, NotebookReference, NotebookReferenceRole,
    TeacherProjectConfiguration, TeacherProjectIdentity,
)

NOTEBOOK_FILENAME = "Systeme-du-premier-ordre-en-regime-transitoire-TPStudio-v2.1.ipynb"


def _plan() -> ScientificProductionPlan:
    return ScientificProductionPlan(
        "first-order-transient-productions",
        "Productions scientifiques — Système du premier ordre en régime transitoire",
        (
            ScientificProductionSpec("charge_graph", "Graphe expérimental de charge uC(t)",
                                     ScientificProductionKind.PLOT, (EvaluationBasis.STRUCTURAL,)),
            ScientificProductionSpec("charge_fit", "Ajustement exponentiel de charge", ScientificProductionKind.QUANTITY,
                                     (EvaluationBasis.STRUCTURAL,), ("charge_graph",)),
            ScientificProductionSpec("tau_comparison", "Comparaison de tau et RC", ScientificProductionKind.COMPARISON,
                                     (EvaluationBasis.STRUCTURAL,), ("charge_fit",)),
            ScientificProductionSpec("energy_values", "Énergies du condensateur et du générateur", ScientificProductionKind.QUANTITY,
                                     (EvaluationBasis.STRUCTURAL,), ("charge_graph",)),
            ScientificProductionSpec("discharge_graph", "Graphe expérimental de décharge", ScientificProductionKind.PLOT,
                                     (EvaluationBasis.STRUCTURAL,)),
            ScientificProductionSpec("leakage_resistance", "Résistance de fuite", ScientificProductionKind.QUANTITY,
                                     (EvaluationBasis.STRUCTURAL,), ("discharge_graph",)),
            ScientificProductionSpec("charge_objective", "Objectif de l'étude de la charge", ScientificProductionKind.INTERPRETATION,
                                     (EvaluationBasis.SEMANTIC,), ("charge_graph", "charge_fit")),
            ScientificProductionSpec("energy_objective", "Objectif de l'étude énergétique", ScientificProductionKind.INTERPRETATION,
                                     (EvaluationBasis.SEMANTIC,), ("energy_values",)),
            ScientificProductionSpec("leakage_objective", "Objectif de l'étude de la fuite", ScientificProductionKind.INTERPRETATION,
                                     (EvaluationBasis.SEMANTIC,), ("discharge_graph", "leakage_resistance")),
            ScientificProductionSpec("leakage_protocol", "Protocole d'observation de la décharge et de détermination de la résistance de fuite", ScientificProductionKind.INTERPRETATION,
                                     (EvaluationBasis.SEMANTIC,), ("discharge_graph",)),
            ScientificProductionSpec("interpretation", "Interprétation des résultats", ScientificProductionKind.INTERPRETATION,
                                     (EvaluationBasis.SEMANTIC,), ("charge_fit", "tau_comparison")),
            ScientificProductionSpec("conclusion", "Conclusion", ScientificProductionKind.INTERPRETATION,
                                     (EvaluationBasis.SEMANTIC,), ("interpretation",)),
        ),
        "Contrat minimal : graphe expérimental uC(t).",
    )


def first_order_transient_teacher_project() -> TeacherProjectConfiguration:
    plan = _plan()
    binding = CellProductionBinding(
        "charge-graph-cell", "charge_graph",
        NotebookCellSelector(NotebookCellSelectorKind.SOURCE_MARKER, "plt.plot(t"),
        CellTextScope.full_source(),
        "Cellule multitracée ; sélection stricte par identité x/y.",
    )
    bindings = NotebookBindingPlan(
        "first-order-transient-bindings", "Associations du TP Premier ordre", plan,
        (binding,), "Le CSV est une source technique injectée séparément.",
    )
    quantities = QuantityExpectationSet(plan, ())
    graphs = GraphExpectationSet(plan, (GraphExpectation(
        production_id="charge_graph", x_expression="t", y_expression="uC",
        accepted_x_labels=("t", "Temps t (s)"),
        accepted_y_labels=("uC", "Tension condensateur uC (V)"),
        regression_required=False, slope_quantity_id=None, index_quantity_id=None,
        slope_index_relation_id=None, legend_required=False,
        description="Graphe expérimental de la tension du condensateur pendant la charge.",
        expected_model=None,
    ),))
    comparisons = QuantityComparisonExpectationSet(plan, quantities, ())
    return TeacherProjectConfiguration(
        TeacherProjectIdentity("first-order-transient", "Système du premier ordre en régime transitoire",
                               "Physique", "Lycée", "A79a", "fr",
                               "Contrat minimal du graphe de charge uC(t)."),
        (NotebookReference("statement", NotebookReferenceRole.STATEMENT, NOTEBOOK_FILENAME),),
        plan, bindings, quantities,
        ExpectationSet("first-order-relations", "Relations attendues — Premier ordre"), None,
        graphs, comparisons, StudentNormalizedErrorExpectationSet(comparisons, ()),
        ComparisonInterpretationExpectationSet(comparisons, ()),
        ComparisonJustificationExpectationSet(comparisons, ()), (),
        "Premier ordre A79a : graphe uC(t) uniquement.",
    )
