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
