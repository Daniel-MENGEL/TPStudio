"""Declarative protocol cells prepared from a TP statement."""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import nbformat
from nbformat.notebooknode import NotebookNode

from tpstudio.feedback import FeedbackAudience, FeedbackPriority
from tpstudio.parsers import LatexParser


class ProtocolStatus(str, Enum):
    PRESENT = "present"
    MISSING = "missing"
    NOT_EVALUABLE = "not_evaluable"


@dataclass(frozen=True, slots=True)
class ExperimentalManipulation:
    stable_id: str
    title: str
    source_section: str
    protocol_expected: bool = True
    source_section_aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("stable_id", "title", "source_section"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} ne peut pas être vide.")
        if type(self.protocol_expected) is not bool:
            raise TypeError("protocol_expected doit être booléen.")
        aliases = tuple(self.source_section_aliases)
        if any(not isinstance(item, str) or not item.strip() for item in aliases):
            raise ValueError("Les alias de section doivent être des chaînes non vides.")
        object.__setattr__(self, "source_section_aliases", aliases)


@dataclass(frozen=True, slots=True)
class ProtocolEvaluation:
    expectation_id: str
    manipulation_id: str
    manipulation_title: str
    status: ProtocolStatus
    cell_index: int | None = None
    cell_type: str | None = None
    anchor_cell_index: int | None = None


@dataclass(frozen=True, slots=True)
class ProtocolDiagnostic:
    expectation_id: str
    manipulation_id: str
    cell_index: int | None
    status: ProtocolStatus
    code: str = "PROTOCOL_EXPECTED_MISSING"
    message_key: str = "Le protocole expérimental de cette manipulation n'est pas décrit."
    source: str = "protocol-cell"


@dataclass(frozen=True, slots=True)
class ProtocolFeedbackItem:
    expectation_id: str
    manipulation_id: str
    text: str
    cell_index: int
    cell_type: str = "markdown"
    audience: FeedbackAudience = FeedbackAudience.STUDENT
    priority: FeedbackPriority = FeedbackPriority.NORMAL
    code: str = "PROTOCOL_EXPECTED_MISSING"
    production_id: str | None = None
    comparison_id: str | None = None

    @property
    def message_key(self) -> str:
        return self.text


def protocol_prompt_source(manipulation: ExperimentalManipulation) -> str:
    return (
        f"## {manipulation.title}\n\n"
        "Décrire précisément le protocole mis en œuvre pour cette manipulation."
    )


def protocol_response_source(manipulation: ExperimentalManipulation) -> str:
    return "### Protocole\n\nÀ compléter : décrire le protocole mis en œuvre."


# Compatibility name retained for the in-progress A73a API.
protocol_cell_source = protocol_response_source


def protocol_cell_metadata(manipulation: ExperimentalManipulation) -> dict:
    return {
        "tpstudio": {
            "role": "protocol_response",
            "expectation_id": manipulation.stable_id,
            "manipulation_id": manipulation.stable_id,
        }
    }


def _normalized(value: str) -> str:
    value = value.replace("’", "'").replace("‘", "'")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value).strip().lower()


def _is_protocol_cell(cell: NotebookNode, expectation_id: str) -> bool:
    metadata = cell.get("metadata", {})
    tpstudio = metadata.get("tpstudio", {}) if isinstance(metadata, dict) else {}
    return (
        isinstance(tpstudio, dict)
        and tpstudio.get("role") == "protocol_response"
        and tpstudio.get("expectation_id") == expectation_id
    )


def _matches_section_marker(source: str, markers: tuple[str, ...]) -> bool:
    for line in source.splitlines():
        candidate = _normalized(re.sub(r"^\s*#+\s*", "", line))
        if candidate in markers:
            return True
    return False


def _content_status(source: str) -> ProtocolStatus:
    text = re.sub(r"(?m)^\s{1,6}#+\s*", "", source)
    text = re.sub(r"[*_`~]", "", text)
    text = re.sub(r"\[[^]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    normalized = _normalized(text)
    placeholders = {
        "",
        "protocole",
        "protocole :",
        "decrire precisement le protocole mis en oeuvre pour cette manipulation.",
        "voir enonce",
        "a completer",
        "à compléter",
        "on fait la manip",
        "on fait la manipulation",
        "mesures",
        "mesure des angles",
    }
    if normalized in {_normalized(item) for item in placeholders}:
        return ProtocolStatus.MISSING
    words = re.findall(r"\b[\wÀ-ÿ'-]+\b", text, flags=re.UNICODE)
    sentences = [part for part in re.split(r"[.!?]+", text) if part.strip()]
    list_items = re.findall(r"(?m)^\s*[-*]\s+\S+", source)
    if (len(words) >= 12 and (len(sentences) >= 2 or len(list_items) >= 2)) or (
        len(words) >= 6 and len(list_items) >= 2
    ):
        return ProtocolStatus.PRESENT
    return ProtocolStatus.MISSING


def evaluate_protocol_cells(
    notebook: NotebookNode,
    manipulations: tuple[ExperimentalManipulation, ...],
) -> tuple[ProtocolEvaluation, ...]:
    """Evaluate only explicitly prepared protocol cells; never scan globally."""

    values: list[ProtocolEvaluation] = []
    for manipulation in manipulations:
        if not manipulation.protocol_expected:
            continue
        matches = [
            (index, cell)
            for index, cell in enumerate(notebook.cells)
            if _is_protocol_cell(cell, manipulation.stable_id)
        ]
        if not matches:
            markers = tuple(_normalized(item) for item in (
                manipulation.source_section, *manipulation.source_section_aliases,
            ))
            anchors = [
                index for index, cell in enumerate(notebook.cells)
                if _matches_section_marker(str(cell.get("source", "")), markers)
            ]
            values.append(ProtocolEvaluation(
                manipulation.stable_id, manipulation.stable_id, manipulation.title,
                ProtocolStatus.MISSING,
                anchor_cell_index=anchors[0] if len(anchors) == 1 else None,
            ))
            continue
        if len(matches) > 1:
            values.append(ProtocolEvaluation(
                manipulation.stable_id, manipulation.stable_id, manipulation.title,
                ProtocolStatus.NOT_EVALUABLE,
            ))
            continue
        index, cell = matches[0]
        if cell.get("cell_type") != "markdown" or not isinstance(cell.get("source"), str):
            values.append(ProtocolEvaluation(
                manipulation.stable_id, manipulation.stable_id, manipulation.title,
                ProtocolStatus.NOT_EVALUABLE, index, cell.get("cell_type"),
            ))
            continue
        values.append(ProtocolEvaluation(
            manipulation.stable_id, manipulation.stable_id, manipulation.title,
            _content_status(cell["source"]), index, "markdown",
        ))
    return tuple(values)


def prepare_notebook_with_protocol_cells(
    notebook: NotebookNode,
    manipulations: tuple[ExperimentalManipulation, ...],
) -> NotebookNode:
    """Return an enriched in-memory copy, preserving existing student cells."""

    prepared = deepcopy(notebook)
    for manipulation in manipulations:
        if not manipulation.protocol_expected:
            continue
        matches = [
            index for index, cell in enumerate(prepared.cells)
            if _is_protocol_cell(cell, manipulation.stable_id)
        ]
        if len(matches) == 1:
            continue
        if len(matches) > 1:
            continue
        markers = tuple(_normalized(item) for item in (
            manipulation.source_section, *manipulation.source_section_aliases,
        ))
        section_index = next(
            (index for index, existing in enumerate(prepared.cells)
             if _matches_section_marker(str(existing.get("source", "")), markers)),
            None,
        )
        if section_index is None:
            prompt = nbformat.v4.new_markdown_cell(protocol_prompt_source(manipulation))
            prompt.metadata = {"tpstudio": {
                "role": "protocol_prompt",
                "manipulation_id": manipulation.stable_id,
            }}
            prepared.cells.append(prompt)
        cell = nbformat.v4.new_markdown_cell(protocol_response_source(manipulation))
        cell.metadata = protocol_cell_metadata(manipulation)
        insertion = next(
            (index + 1 for index, existing in enumerate(prepared.cells)
             if _matches_section_marker(str(existing.get("source", "")), markers)),
            len(prepared.cells),
        )
        prepared.cells.insert(insertion, cell)
    return prepared


def prepare_notebook_file(
    source_path: str | Path,
    destination_path: str | Path,
    manipulations: tuple[ExperimentalManipulation, ...],
) -> None:
    source = nbformat.read(Path(source_path), as_version=4)
    prepared = prepare_notebook_with_protocol_cells(source, manipulations)
    nbformat.write(prepared, Path(destination_path))


def snells_laws_manipulations() -> tuple[ExperimentalManipulation, ...]:
    return (
        ExperimentalManipulation(
            "protocol-first-index-method",
            "Première méthode de mesure de l'indice",
            "Première méthode de mesure de l'indice",
            source_section_aliases=("1. Mesure par angle limite",),
        ),
        ExperimentalManipulation(
            "protocol-second-index-method",
            "Seconde méthode de mesure de l'indice",
            "Seconde méthode de mesure de l'indice",
            source_section_aliases=("2. Mesure avec un seul couple d'angles",),
        ),
        ExperimentalManipulation(
            "protocol-refraction-law",
            "Vérification de la loi de la réfraction et dernière méthode de mesure de l'indice",
            "Vérification de la loi de la réfraction et dernière méthode de mesure de l'indice",
            source_section_aliases=("3. Vérification graphique de la loi de la réfraction",),
        ),
    )


def manipulations_from_latex(path: str | Path) -> tuple[ExperimentalManipulation, ...]:
    """Extract section-shaped manipulations from a structured LaTeX statement."""

    document = LatexParser(path).parse()
    values: list[ExperimentalManipulation] = []
    known = {
        "premiere methode de mesure de l'indice": "protocol-first-index-method",
        "seconde methode de mesure de l'indice": "protocol-second-index-method",
        "verification de la loi de la refraction et derniere methode de mesure de l'indice": "protocol-refraction-law",
    }
    for index, section in enumerate(document.sections, 1):
        title = section.title.strip()
        normalized = _normalized(title)
        if "presentation du dispositif" in normalized:
            continue
        if not any(token in normalized for token in ("methode", "manipulation", "experience")):
            continue
        values.append(ExperimentalManipulation(
            known.get(normalized, f"protocol-manipulation-{index:03d}"), title, title,
        ))
    return tuple(values)
