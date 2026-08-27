"""Versioned teacher-project configurations."""

from .model import (
    GraphExpectation,
    GraphExpectationSet,
    ExpectedGraphModel,
    NotebookReference,
    NotebookReferenceRole,
    TeacherProjectConfiguration,
    TeacherProjectIdentity,
    summarize_teacher_project_configuration,
    validate_teacher_project_configuration,
)
from .snells_laws import snells_laws_teacher_project
from .thin_lens import thin_lens_teacher_project
from .focometry import (
    CORRECTION_FILENAME as FOCOMETRY_CORRECTION_FILENAME,
    SEMANTIC_RESPONSE_EXPECTATIONS as FOCOMETRY_SEMANTIC_EXPECTATIONS,
    STATEMENT_FILENAME as FOCOMETRY_STATEMENT_FILENAME,
    focometry_teacher_project,
)
from .torsion_pendulum import torsion_pendulum_teacher_project
from .first_order_transient import (
    CHARGE_OBJECTIVE_SEMANTIC_CONTRACT,
    ENERGY_OBJECTIVE_SEMANTIC_CONTRACT,
    LEAKAGE_PROTOCOL_SEMANTIC_CONTRACT,
    first_order_transient_teacher_project,
)
from .first_lab_measurements import (
    CORRECTION_FILENAME as FIRST_LAB_MEASUREMENTS_CORRECTION_FILENAME,
    SEMANTIC_RESPONSE_EXPECTATIONS as FIRST_LAB_MEASUREMENTS_SEMANTIC_EXPECTATIONS,
    STATEMENT_FILENAME as FIRST_LAB_MEASUREMENTS_STATEMENT_FILENAME,
    first_lab_measurements_teacher_project,
)
from .graph_model_inference import (
    ExpectedGraphModelProposal,
    ExpectedModelProposalConfidence,
    ExpectedModelProposalSource,
    infer_expected_graph_model,
)
from .project_resolution import (
    PROJECT_DESCRIPTORS,
    ProjectDescriptor,
    ProjectEvidenceCategory,
    ProjectResolutionCandidate,
    ProjectResolutionConfidence,
    ProjectResolutionEvidence,
    ProjectResolutionResult,
    extract_project_signatures,
    known_project_ids,
    project_descriptor,
    resolve_project_for_copy,
)

__all__ = [
    "GraphExpectation",
    "GraphExpectationSet",
    "ExpectedGraphModel",
    "NotebookReference",
    "NotebookReferenceRole",
    "TeacherProjectConfiguration",
    "TeacherProjectIdentity",
    "snells_laws_teacher_project",
    "thin_lens_teacher_project",
    "focometry_teacher_project",
    "FOCOMETRY_STATEMENT_FILENAME",
    "FOCOMETRY_CORRECTION_FILENAME",
    "FOCOMETRY_SEMANTIC_EXPECTATIONS",
    "torsion_pendulum_teacher_project",
    "first_order_transient_teacher_project",
    "first_lab_measurements_teacher_project",
    "FIRST_LAB_MEASUREMENTS_STATEMENT_FILENAME",
    "FIRST_LAB_MEASUREMENTS_CORRECTION_FILENAME",
    "FIRST_LAB_MEASUREMENTS_SEMANTIC_EXPECTATIONS",
    "CHARGE_OBJECTIVE_SEMANTIC_CONTRACT",
    "ENERGY_OBJECTIVE_SEMANTIC_CONTRACT",
    "LEAKAGE_PROTOCOL_SEMANTIC_CONTRACT",
    "summarize_teacher_project_configuration",
    "validate_teacher_project_configuration",
    "ExpectedGraphModelProposal",
    "ExpectedModelProposalConfidence",
    "ExpectedModelProposalSource",
    "infer_expected_graph_model",
    "PROJECT_DESCRIPTORS",
    "ProjectDescriptor",
    "ProjectEvidenceCategory",
    "ProjectResolutionCandidate",
    "ProjectResolutionConfidence",
    "ProjectResolutionEvidence",
    "ProjectResolutionResult",
    "extract_project_signatures",
    "known_project_ids",
    "project_descriptor",
    "resolve_project_for_copy",
]
