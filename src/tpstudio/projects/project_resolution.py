"""Pure, conservative project resolution from static notebook signatures.

This module does not execute notebooks and is deliberately independent from
scientific analysis, reporting, batch execution, and the Web layer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Callable

from .model import TeacherProjectConfiguration
from .snells_laws import snells_laws_teacher_project
from .thin_lens import thin_lens_teacher_project
from .torsion_pendulum import torsion_pendulum_teacher_project


class ProjectResolutionConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ProjectEvidenceCategory(str, Enum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


@dataclass(frozen=True, slots=True)
class ProjectResolutionEvidence:
    kind: str
    text: str
    category: ProjectEvidenceCategory

    def __post_init__(self) -> None:
        for name in ("kind", "text"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} doit être une chaîne non vide.")
        if type(self.category) is not ProjectEvidenceCategory:
            raise TypeError("La catégorie d'indice est invalide.")


@dataclass(frozen=True, slots=True)
class ProjectResolutionCandidate:
    project_id: str
    confidence: ProjectResolutionConfidence
    evidence: tuple[ProjectResolutionEvidence, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.project_id, str) or not self.project_id.strip():
            raise ValueError("project_id doit être une chaîne non vide.")
        if type(self.confidence) is not ProjectResolutionConfidence:
            raise TypeError("La confiance du candidat est invalide.")
        evidence = tuple(self.evidence)
        if any(type(item) is not ProjectResolutionEvidence for item in evidence):
            raise TypeError("Les indices du candidat sont invalides.")
        object.__setattr__(self, "evidence", evidence)


@dataclass(frozen=True, slots=True)
class ProjectResolutionResult:
    selected_project_id: str | None
    candidates: tuple[ProjectResolutionCandidate, ...]
    requires_teacher_choice: bool

    def __post_init__(self) -> None:
        candidates = tuple(self.candidates)
        if any(type(item) is not ProjectResolutionCandidate for item in candidates):
            raise TypeError("Les candidats de résolution sont invalides.")
        if len({item.project_id for item in candidates}) != len(candidates):
            raise ValueError("Les candidats doivent avoir des project_id distincts.")
        if self.selected_project_id is not None and self.selected_project_id not in {
            item.project_id for item in candidates
        }:
            raise ValueError("Le projet sélectionné doit être un candidat.")
        if type(self.requires_teacher_choice) is not bool:
            raise TypeError("requires_teacher_choice doit être booléen.")
        object.__setattr__(self, "candidates", candidates)


@dataclass(frozen=True, slots=True)
class ProjectDescriptor:
    project_id: str
    title: str
    factory: Callable[[], TeacherProjectConfiguration]
    matcher: Callable[[str, str, str], tuple[ProjectResolutionEvidence, ...]]

    def __post_init__(self) -> None:
        if not isinstance(self.project_id, str) or not self.project_id.strip():
            raise ValueError("project_id doit être une chaîne non vide.")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title doit être une chaîne non vide.")
        if not callable(self.factory):
            raise TypeError("factory doit être appelable.")
        if not callable(self.matcher):
            raise TypeError("matcher doit être appelable.")


def known_project_ids() -> tuple[str, ...]:
    """Return project identifiers in stable registry order."""
    return tuple(item.project_id for item in PROJECT_DESCRIPTORS)


def project_descriptor(project_id: str) -> ProjectDescriptor | None:
    return next((item for item in PROJECT_DESCRIPTORS if item.project_id == project_id), None)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _notebook_cells(notebook: Any) -> tuple[tuple[str, str], ...]:
    cells = getattr(notebook, "cells", None)
    if cells is None and isinstance(notebook, Mapping):
        cells = notebook.get("cells")
    if cells is None:
        if isinstance(notebook, Sequence) and not isinstance(notebook, (str, bytes)):
            cells = notebook
        else:
            raise TypeError("Le notebook doit exposer des cellules statiques.")
    result: list[tuple[str, str]] = []
    for cell in cells:
        if isinstance(cell, Mapping):
            cell_type, source = cell.get("cell_type"), cell.get("source", "")
            metadata = cell.get("metadata", {})
        else:
            cell_type, source = getattr(cell, "cell_type", None), getattr(cell, "source", "")
            metadata = getattr(cell, "metadata", {})
        if not isinstance(source, str):
            continue
        result.append((str(cell_type or ""), source + "\n" + str(metadata)))
    return tuple(result)


def extract_project_signatures(notebook: Any, *, filename: str | None = None) -> tuple[ProjectResolutionEvidence, ...]:
    """Extract generic static evidence without identifying or executing a notebook."""
    cells = _notebook_cells(notebook)
    markdown = "\n".join(source for kind, source in cells if kind == "markdown")
    code = "\n".join(source for kind, source in cells if kind == "code")
    evidence: list[ProjectResolutionEvidence] = []
    if markdown:
        first_heading = next((line.strip() for line in markdown.splitlines() if line.lstrip().startswith("#")), None)
        if first_heading:
            evidence.append(ProjectResolutionEvidence("heading", first_heading[:180], ProjectEvidenceCategory.MEDIUM))
    if filename:
        evidence.append(ProjectResolutionEvidence("filename", filename, ProjectEvidenceCategory.WEAK))
    if code:
        evidence.append(ProjectResolutionEvidence("code", "Signatures de code statiques présentes", ProjectEvidenceCategory.WEAK))
    if markdown:
        evidence.append(ProjectResolutionEvidence("markdown", "Cellules Markdown présentes", ProjectEvidenceCategory.WEAK))
    return tuple(evidence)


def _text_for(notebook: Any, filename: str | None) -> tuple[str, str, str]:
    cells = _notebook_cells(notebook)
    markdown = "\n".join(source for kind, source in cells if kind == "markdown")
    code = "\n".join(source for kind, source in cells if kind == "code")
    return _normalise(markdown), _normalise(code), _normalise(filename or "")


def _evidence(kind: str, text: str, category: ProjectEvidenceCategory) -> ProjectResolutionEvidence:
    return ProjectResolutionEvidence(kind, text[:180], category)


def _snell_evidence(markdown: str, code: str, filename: str) -> tuple[ProjectResolutionEvidence, ...]:
    evidence: list[ProjectResolutionEvidence] = []
    if re.search(r"lois?\s+de\s+snell|snell[- ]descartes", markdown):
        evidence.append(_evidence("title", "Titre Snell-Descartes", ProjectEvidenceCategory.STRONG))
    if re.search(r"r[eé]fraction|loi\s+de\s+snell|indice\s+de\s+r[eé]fraction", markdown):
        evidence.append(_evidence("relation", "Réfraction / indice de réfraction", ProjectEvidenceCategory.STRONG))
    if re.search(r"sin\s*\(?\s*i\s*[12]\s*\)?", markdown + code) and re.search(r"i\s*[12]", markdown + code):
        evidence.append(_evidence("quantities", "Angles i1/i2 et sinus", ProjectEvidenceCategory.MEDIUM))
    if "indice" in markdown and "réfraction" in markdown:
        evidence.append(_evidence("vocabulary", "Indice et réfraction", ProjectEvidenceCategory.MEDIUM))
    if re.search(r"snell|descartes", filename):
        evidence.append(_evidence("filename", filename, ProjectEvidenceCategory.WEAK))
    return tuple(evidence)


def _thin_lens_evidence(markdown: str, code: str, filename: str) -> tuple[ProjectResolutionEvidence, ...]:
    evidence: list[ProjectResolutionEvidence] = []
    if re.search(r"formation\s+d['’]une\s+image\s+par\s+une\s+lentille\s+mince", markdown):
        evidence.append(_evidence("title", "Titre Lentille mince", ProjectEvidenceCategory.STRONG))
    if re.search(r"relation\s+de\s+conjugaison|1\s*/\s*oa['’]?\s*[-=]", markdown):
        evidence.append(_evidence("relation", "Relation de conjugaison", ProjectEvidenceCategory.STRONG))
    if re.search(r"distance\s+focale|oa['’]?|oa\b", markdown) and re.search(r"d0|d1|d2|invoa", markdown + code):
        evidence.append(_evidence("quantities", "OA/OA' et distances d0/d1/d2", ProjectEvidenceCategory.MEDIUM))
    if "lentille mince" in markdown or "distance focale" in markdown:
        evidence.append(_evidence("vocabulary", "Vocabulaire de lentille", ProjectEvidenceCategory.MEDIUM))
    if re.search(r"lentille|mince", filename):
        evidence.append(_evidence("filename", filename, ProjectEvidenceCategory.WEAK))
    return tuple(evidence)


def _torsion_pendulum_evidence(markdown: str, code: str, filename: str) -> tuple[ProjectResolutionEvidence, ...]:
    evidence: list[ProjectResolutionEvidence] = []
    if re.search(r"pendule\s+de\s+torsion", markdown):
        evidence.append(_evidence("title", "Titre Pendule de torsion", ProjectEvidenceCategory.STRONG))
    if re.search(r"T_0|J_b|m_susp|theta_eq", code):
        evidence.append(_evidence("code", "Variables caractéristiques du pendule de torsion", ProjectEvidenceCategory.MEDIUM))
    if re.search(r"pendule[- ]de[- ]torsion", filename):
        evidence.append(_evidence("filename", filename, ProjectEvidenceCategory.WEAK))
    return tuple(evidence)


PROJECT_DESCRIPTORS: tuple[ProjectDescriptor, ...] = (
    ProjectDescriptor("snells-laws-mvp", "Lois de Snell-Descartes", snells_laws_teacher_project, _snell_evidence),
    ProjectDescriptor("thin-lens-image", "Formation d'une image par une lentille mince", thin_lens_teacher_project, _thin_lens_evidence),
    ProjectDescriptor("torsion-pendulum", "Pendule de torsion", torsion_pendulum_teacher_project, _torsion_pendulum_evidence),
)


def _candidate_for(descriptor: ProjectDescriptor, markdown: str, code: str, filename: str) -> ProjectResolutionCandidate | None:
    evidence = list(descriptor.matcher(markdown, code, filename))
    if not evidence:
        return None
    strong = sum(item.category is ProjectEvidenceCategory.STRONG for item in evidence)
    medium = sum(item.category is ProjectEvidenceCategory.MEDIUM for item in evidence)
    weak = sum(item.category is ProjectEvidenceCategory.WEAK for item in evidence)
    confidence = (
        ProjectResolutionConfidence.HIGH if strong or medium >= 2
        else ProjectResolutionConfidence.MEDIUM if medium or weak
        else ProjectResolutionConfidence.LOW
    )
    # A filename or code hint alone is deliberately never HIGH.
    if strong == 0 and medium == 0:
        confidence = ProjectResolutionConfidence.LOW
    return ProjectResolutionCandidate(descriptor.project_id, confidence, tuple(evidence[:6]))


def resolve_project_for_copy(
    notebook: Any,
    *,
    filename: str | None = None,
    explicit_project_id: str | None = None,
    descriptors: Sequence[ProjectDescriptor] = PROJECT_DESCRIPTORS,
) -> ProjectResolutionResult:
    """Resolve a project from static signatures, abstaining when uncertain."""
    descriptors = tuple(descriptors)
    if explicit_project_id is not None:
        if not any(item.project_id == explicit_project_id for item in descriptors):
            raise ValueError(f"Projet inconnu : {explicit_project_id!r}.")
        return ProjectResolutionResult(
            explicit_project_id,
            (ProjectResolutionCandidate(
                explicit_project_id, ProjectResolutionConfidence.HIGH,
                (_evidence("explicit", "Projet fourni explicitement", ProjectEvidenceCategory.STRONG),),
            ),),
            False,
        )
    markdown, code, name = _text_for(notebook, filename)
    candidates = tuple(
        candidate
        for descriptor in descriptors
        if (candidate := _candidate_for(descriptor, markdown, code, name)) is not None
    )
    if not candidates:
        return ProjectResolutionResult(None, (), False)
    highs = tuple(item for item in candidates if item.confidence is ProjectResolutionConfidence.HIGH)
    if len(highs) == 1:
        return ProjectResolutionResult(highs[0].project_id, candidates, False)
    return ProjectResolutionResult(None, candidates, True)
