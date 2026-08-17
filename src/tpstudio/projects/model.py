"""Immutable teacher-project configuration contracts."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from tpstudio.expectations import (
    ComparisonInterpretationExpectationSet,
    ComparisonJustificationExpectationSet,
    ExpectationSet,
    NotebookBindingPlan,
    QuantityComparisonExpectationSet,
    QuantityExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    StudentNormalizedErrorExpectationSet,
    UncertaintyQualityExpectationSet,
)
from tpstudio.feedback import (
    ComparisonInterpretationFeedbackCatalog,
    ComparisonJustificationFeedbackCatalog,
    QuantityComparisonFeedbackCatalog,
    QuantityFeedbackCatalog,
)
from tpstudio.protocol import ExperimentalManipulation


def _required_text(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"Le champ {field_name!r} doit être une chaîne.")
    if not value.strip():
        raise ValueError(f"Le champ {field_name!r} ne peut pas être vide.")


@dataclass(frozen=True, slots=True)
class TeacherProjectIdentity:
    project_id: str
    title: str
    subject: str
    level: str
    version: str
    language: str = "fr"
    description: str = ""

    def __post_init__(self) -> None:
        for name in ("project_id", "title", "subject", "level", "version", "language"):
            _required_text(getattr(self, name), name)
        if not isinstance(self.description, str):
            raise TypeError("La description doit être une chaîne.")


class NotebookReferenceRole(str, Enum):
    STATEMENT = "statement"
    CORRECTION = "correction"
    CONTROL_COPY = "control_copy"


class ExpectedGraphModel(str, Enum):
    """Mathematical form declared by the teacher for one expected graph."""

    LINEAR_THROUGH_ORIGIN = "linear_through_origin"
    AFFINE = "affine"
    QUADRATIC = "quadratic"


@dataclass(frozen=True, slots=True)
class NotebookReference:
    reference_id: str
    role: NotebookReferenceRole
    expected_filename: str
    content_fingerprint: str | None = None
    description: str = ""

    def __post_init__(self) -> None:
        _required_text(self.reference_id, "reference_id")
        if type(self.role) is not NotebookReferenceRole:
            raise TypeError("Le rôle doit être un NotebookReferenceRole.")
        _required_text(self.expected_filename, "expected_filename")
        filename = self.expected_filename
        if "/" in filename or "\\" in filename or filename.startswith("~"):
            raise ValueError("Le nom attendu doit être un simple nom de fichier.")
        if self.content_fingerprint is not None:
            _required_text(self.content_fingerprint, "content_fingerprint")
        if not isinstance(self.description, str):
            raise TypeError("La description doit être une chaîne.")


@dataclass(frozen=True, slots=True)
class GraphExpectation:
    production_id: str
    x_expression: str
    y_expression: str
    accepted_x_labels: tuple[str, ...]
    accepted_y_labels: tuple[str, ...]
    regression_required: bool
    slope_quantity_id: str
    index_quantity_id: str | None
    slope_index_relation_id: str
    title_required: bool = False
    legend_required: bool = True
    description: str = ""
    expected_model: ExpectedGraphModel | None = None

    def __post_init__(self) -> None:
        for name in (
            "production_id", "x_expression", "y_expression", "slope_quantity_id",
            "slope_index_relation_id",
        ):
            _required_text(getattr(self, name), name)
        if self.index_quantity_id is not None:
            _required_text(self.index_quantity_id, "index_quantity_id")
        for name in ("accepted_x_labels", "accepted_y_labels"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)):
                raise TypeError("Les labels doivent former une collection ordonnée.")
            labels = tuple(value)
            if not labels:
                raise ValueError("Au moins un label doit être déclaré par axe.")
            if any(not isinstance(label, str) or not label.strip() for label in labels):
                raise ValueError("Un label d'axe ne peut pas être vide.")
            if len(labels) != len(set(labels)):
                raise ValueError("Les labels d'un axe doivent être uniques.")
            object.__setattr__(self, name, labels)
        for name in ("regression_required", "title_required", "legend_required"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"Le champ {name!r} doit être un booléen.")
        if self.expected_model is not None and type(self.expected_model) is not ExpectedGraphModel:
            raise TypeError("Le modèle attendu doit être un ExpectedGraphModel ou None.")
        if not isinstance(self.description, str):
            raise TypeError("La description doit être une chaîne.")


@dataclass(frozen=True, slots=True)
class GraphExpectationSet:
    production_plan: ScientificProductionPlan
    graphs: tuple[GraphExpectation, ...]

    def __post_init__(self) -> None:
        if type(self.production_plan) is not ScientificProductionPlan:
            raise TypeError("Le plan scientifique est invalide.")
        if isinstance(self.graphs, (str, bytes)):
            raise TypeError("Les graphes doivent former une collection.")
        graphs = tuple(self.graphs)
        if not graphs:
            raise ValueError("Au moins un graphe est requis.")
        if any(type(graph) is not GraphExpectation for graph in graphs):
            raise TypeError("Chaque graphe doit être un GraphExpectation.")
        ids = tuple(graph.production_id for graph in graphs)
        if len(ids) != len(set(ids)):
            raise ValueError("Les productions de graphe doivent être uniques.")
        for graph in graphs:
            production = self.production_plan.get(graph.production_id)
            if production is None or production.kind is not ScientificProductionKind.PLOT:
                raise ValueError("Un graphe doit cibler une production PLOT connue.")
            for quantity_id in (graph.slope_quantity_id, graph.index_quantity_id):
                if quantity_id is None:
                    continue
                quantity = self.production_plan.get(quantity_id)
                if quantity is None or quantity.kind is not ScientificProductionKind.QUANTITY:
                    raise ValueError("Le graphe référence une quantité inconnue.")
        object.__setattr__(self, "graphs", graphs)

    def __iter__(self) -> Iterator[GraphExpectation]:
        return iter(self.graphs)

    def get(self, production_id: str) -> GraphExpectation | None:
        return next((item for item in self.graphs if item.production_id == production_id), None)


_CATALOG_TYPES = (
    QuantityFeedbackCatalog,
    QuantityComparisonFeedbackCatalog,
    ComparisonInterpretationFeedbackCatalog,
    ComparisonJustificationFeedbackCatalog,
)


@dataclass(frozen=True, slots=True)
class TeacherProjectConfiguration:
    identity: TeacherProjectIdentity
    notebook_references: tuple[NotebookReference, ...]
    scientific_production_plan: ScientificProductionPlan
    notebook_binding_plan: NotebookBindingPlan
    quantity_expectation_set: QuantityExpectationSet
    relation_expectation_set: ExpectationSet
    uncertainty_expectation_set: UncertaintyQualityExpectationSet | None
    graph_expectation_set: GraphExpectationSet | None
    quantity_comparison_expectation_set: QuantityComparisonExpectationSet
    student_normalized_error_expectation_set: StudentNormalizedErrorExpectationSet
    comparison_interpretation_expectation_set: ComparisonInterpretationExpectationSet
    comparison_justification_expectation_set: ComparisonJustificationExpectationSet
    feedback_catalogs: tuple[object, ...]
    description: str = ""
    experimental_manipulations: tuple[ExperimentalManipulation, ...] = ()

    def __post_init__(self) -> None:
        validate_teacher_project_configuration(self, normalize=True)

    @property
    def statement_reference(self) -> NotebookReference:
        return next(item for item in self.notebook_references if item.role is NotebookReferenceRole.STATEMENT)

    @property
    def correction_reference(self) -> NotebookReference | None:
        return next((item for item in self.notebook_references if item.role is NotebookReferenceRole.CORRECTION), None)

    @property
    def control_copy_reference(self) -> NotebookReference | None:
        return next((item for item in self.notebook_references if item.role is NotebookReferenceRole.CONTROL_COPY), None)

    def get_notebook_reference(self, reference_id: str) -> NotebookReference | None:
        return next((item for item in self.notebook_references if item.reference_id == reference_id), None)

    def get_production(self, production_id: str):
        return self.scientific_production_plan.get(production_id)

    def get_comparison(self, comparison_id: str):
        return self.quantity_comparison_expectation_set.get(comparison_id)


def validate_teacher_project_configuration(
    configuration: TeacherProjectConfiguration,
    *,
    normalize: bool = False,
) -> None:
    """Validate cross-contract identity without reading external data."""

    if type(configuration) is not TeacherProjectConfiguration:
        raise TypeError("La configuration doit être un TeacherProjectConfiguration.")
    if type(configuration.identity) is not TeacherProjectIdentity:
        raise TypeError("L'identité du projet est invalide.")
    references = configuration.notebook_references
    if isinstance(references, (str, bytes)):
        raise TypeError("Les références doivent former une collection.")
    references = tuple(references)
    if any(type(item) is not NotebookReference for item in references):
        raise TypeError("Chaque référence de notebook est invalide.")
    if len({item.reference_id for item in references}) != len(references):
        raise ValueError("Les identifiants de notebook doivent être uniques.")
    counts = {role: sum(item.role is role for item in references) for role in NotebookReferenceRole}
    if counts[NotebookReferenceRole.STATEMENT] != 1:
        raise ValueError("Le projet exige exactement un énoncé.")
    if counts[NotebookReferenceRole.CORRECTION] > 1 or counts[NotebookReferenceRole.CONTROL_COPY] > 1:
        raise ValueError("Le projet accepte au plus un corrigé et une copie contrôlée.")
    if normalize:
        object.__setattr__(configuration, "notebook_references", references)

    manipulations = tuple(configuration.experimental_manipulations)
    if any(type(item) is not ExperimentalManipulation for item in manipulations):
        raise TypeError("Chaque manipulation doit être une ExperimentalManipulation.")
    manipulation_ids = tuple(item.stable_id for item in manipulations)
    if len(manipulation_ids) != len(set(manipulation_ids)):
        raise ValueError("Les identifiants de manipulation doivent être uniques.")
    if normalize:
        object.__setattr__(configuration, "experimental_manipulations", manipulations)

    plan = configuration.scientific_production_plan
    if type(plan) is not ScientificProductionPlan:
        raise TypeError("Le plan scientifique est invalide.")
    if type(configuration.notebook_binding_plan) is not NotebookBindingPlan or configuration.notebook_binding_plan.production_plan is not plan:
        raise ValueError("Les bindings doivent partager le plan scientifique.")
    quantities = configuration.quantity_expectation_set
    if type(quantities) is not QuantityExpectationSet or quantities.plan is not plan:
        raise ValueError("Les quantités doivent partager le plan scientifique.")
    relations = configuration.relation_expectation_set
    if type(relations) is not ExpectationSet:
        raise TypeError("Les relations doivent former un ExpectationSet.")
    relation_productions = {item.id for item in relations.relations}
    if any(
        plan.get(identifier) is None
        or plan.get(identifier).kind is not ScientificProductionKind.RELATION
        for identifier in relation_productions
    ):
        raise ValueError("Chaque relation doit cibler une production RELATION.")
    uncertainties = configuration.uncertainty_expectation_set
    if uncertainties is not None and (
        type(uncertainties) is not UncertaintyQualityExpectationSet
        or uncertainties.quantity_expectation_set is not quantities
    ):
        raise ValueError("Les incertitudes doivent partager les quantités.")
    graphs = configuration.graph_expectation_set
    if graphs is not None and (
        type(graphs) is not GraphExpectationSet or graphs.production_plan is not plan
    ):
        raise ValueError("Les graphes doivent partager le plan scientifique.")
    if graphs is not None and any(
        relations.relation_by_id(graph.slope_index_relation_id) is None for graph in graphs
    ):
        raise ValueError("La relation pente–indice du graphe est inconnue.")
    comparisons = configuration.quantity_comparison_expectation_set
    if type(comparisons) is not QuantityComparisonExpectationSet or comparisons.production_plan is not plan or comparisons.quantity_expectation_set is not quantities:
        raise ValueError("Les comparaisons doivent partager le plan et les quantités.")
    dependents = (
        (configuration.student_normalized_error_expectation_set, StudentNormalizedErrorExpectationSet),
        (configuration.comparison_interpretation_expectation_set, ComparisonInterpretationExpectationSet),
        (configuration.comparison_justification_expectation_set, ComparisonJustificationExpectationSet),
    )
    for dependent, expected_type in dependents:
        if type(dependent) is not expected_type:
            raise TypeError("Un jeu d'attentes A70 est d'un type invalide.")
    for dependent, _ in dependents:
        if dependent.comparison_expectation_set is not comparisons:
            raise ValueError("Les attentes A70 doivent partager les comparaisons.")
    catalogs = configuration.feedback_catalogs
    if isinstance(catalogs, (str, bytes)):
        raise TypeError("Les catalogues doivent former une collection.")
    catalogs = tuple(catalogs)
    if not catalogs or any(type(item) not in _CATALOG_TYPES for item in catalogs):
        raise TypeError("Chaque catalogue doit être un catalogue public pris en charge.")
    if len({type(item) for item in catalogs}) != len(catalogs):
        raise ValueError("Un type de catalogue ne peut apparaître qu'une fois.")
    if normalize:
        object.__setattr__(configuration, "feedback_catalogs", catalogs)
    if not isinstance(configuration.description, str):
        raise TypeError("La description doit être une chaîne.")


def summarize_teacher_project_configuration(configuration: TeacherProjectConfiguration) -> str:
    validate_teacher_project_configuration(configuration)
    lines = [
        f"Projet : {configuration.identity.title} ({configuration.identity.project_id})",
        f"Niveau : {configuration.identity.level} — version {configuration.identity.version}",
        "Références :",
    ]
    lines.extend(
        f"- {item.role.value}: {item.expected_filename}" for item in configuration.notebook_references
    )
    lines.append("Productions :")
    lines.extend(
        f"- {item.id} [{item.kind.value}]" for item in configuration.scientific_production_plan.evaluation_order
    )
    lines.append("Quantités : " + ", ".join(item.production_id for item in configuration.quantity_expectation_set))
    lines.append("Relations : " + ", ".join(item.id for item in configuration.relation_expectation_set.relations))
    lines.append("Graphes : " + ", ".join(item.production_id for item in configuration.graph_expectation_set or ()))
    lines.append("Comparaisons : " + ", ".join(item.production_id for item in configuration.quantity_comparison_expectation_set))
    lines.append("En étudiant : " + ", ".join(item.comparison_id for item in configuration.student_normalized_error_expectation_set))
    lines.append("Interprétations : " + ", ".join(item.comparison_id for item in configuration.comparison_interpretation_expectation_set))
    lines.append("Justifications : " + ", ".join(item.comparison_id for item in configuration.comparison_justification_expectation_set))
    lines.append("Catalogues : " + ", ".join(type(item).__name__ for item in configuration.feedback_catalogs))
    return "\n".join(lines)
