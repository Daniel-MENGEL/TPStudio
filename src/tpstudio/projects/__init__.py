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
]
