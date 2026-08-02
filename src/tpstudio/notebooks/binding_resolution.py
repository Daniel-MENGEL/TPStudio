"""Read-only resolution of declared bindings in an in-memory notebook."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from nbformat.notebooknode import NotebookNode

from tpstudio.expectations.notebook_bindings import (
    CellProductionBinding,
    CellTextScope,
    CellTextScopeKind,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
)


class NotebookBindingResolutionStatus(str, Enum):
    """Technical outcome of resolving one declared notebook binding."""

    RESOLVED = "resolved"
    CELL_NOT_FOUND = "cell_not_found"
    CELL_AMBIGUOUS = "cell_ambiguous"
    TEXT_MARKER_NOT_FOUND = "text_marker_not_found"
    TEXT_MARKER_AMBIGUOUS = "text_marker_ambiguous"


def _validate_index(value: object, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} doit être un entier non booléen.")
    if value < 0:
        raise ValueError(f"{field_name} ne peut pas être négatif.")


@dataclass(frozen=True, slots=True)
class NotebookCellReference:
    """Immutable identity of one observed cell, without its source."""

    index: int
    cell_type: str
    cell_id: str | None
    tags: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_index(self.index, "L'index de cellule")
        if not isinstance(self.cell_type, str):
            raise TypeError("Le type de cellule doit être une chaîne.")
        if not self.cell_type.strip():
            raise ValueError("Le type de cellule ne peut pas être vide.")
        if self.cell_id is not None and not isinstance(self.cell_id, str):
            raise TypeError("L'identifiant de cellule doit être une chaîne ou None.")
        if isinstance(self.tags, (str, bytes)):
            raise TypeError("Les tags de cellule doivent former une collection.")
        tags = tuple(self.tags)
        if any(not isinstance(tag, str) for tag in tags):
            raise TypeError("Chaque tag de cellule doit être une chaîne.")
        object.__setattr__(self, "tags", tags)


@dataclass(frozen=True, slots=True)
class NotebookBindingResolution:
    """Auditable technical resolution of one declared binding."""

    binding: CellProductionBinding
    status: NotebookBindingResolutionStatus
    candidate_indices: tuple[int, ...] = ()
    cell: NotebookCellReference | None = None
    text: str | None = None
    text_start: int | None = None
    text_end: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.binding, CellProductionBinding):
            raise TypeError("Le rattachement doit être un CellProductionBinding.")
        if not isinstance(self.status, NotebookBindingResolutionStatus):
            raise TypeError("Le statut doit être un NotebookBindingResolutionStatus.")
        candidates = tuple(self.candidate_indices)
        for index in candidates:
            _validate_index(index, "L'indice candidat")
        if any(left >= right for left, right in zip(candidates, candidates[1:])):
            raise ValueError("Les indices candidats doivent être strictement croissants.")
        object.__setattr__(self, "candidate_indices", candidates)
        if self.cell is not None and not isinstance(self.cell, NotebookCellReference):
            raise TypeError("La cellule doit être une NotebookCellReference ou None.")
        for boundary in (self.text_start, self.text_end):
            if boundary is not None:
                _validate_index(boundary, "La borne textuelle")

        if self.status is NotebookBindingResolutionStatus.RESOLVED:
            if len(candidates) != 1 or self.cell is None:
                raise ValueError("Une résolution réussie exige une cellule unique.")
            if self.cell.index != candidates[0]:
                raise ValueError("La cellule doit correspondre à l'indice candidat.")
            if not isinstance(self.text, str):
                raise TypeError("Une résolution réussie exige un texte.")
            if self.text_start is None or self.text_end is None:
                raise ValueError("Une résolution réussie exige deux bornes textuelles.")
            if self.text_start > self.text_end:
                raise ValueError("La borne de début ne peut pas dépasser la fin.")
            if len(self.text) != self.text_end - self.text_start:
                raise ValueError("Le texte ne correspond pas aux bornes déclarées.")
            return

        if self.text is not None or self.text_start is not None or self.text_end is not None:
            raise ValueError("Une résolution en échec ne contient aucun fragment textuel.")
        if self.status is NotebookBindingResolutionStatus.CELL_NOT_FOUND:
            if candidates or self.cell is not None:
                raise ValueError("Une cellule absente ne possède aucun candidat.")
        elif self.status is NotebookBindingResolutionStatus.CELL_AMBIGUOUS:
            if len(candidates) < 2 or self.cell is not None:
                raise ValueError("Une cellule ambiguë exige plusieurs candidats.")
        elif self.status in (
            NotebookBindingResolutionStatus.TEXT_MARKER_NOT_FOUND,
            NotebookBindingResolutionStatus.TEXT_MARKER_AMBIGUOUS,
        ):
            if len(candidates) != 1 or self.cell is None:
                raise ValueError("Un échec de marqueur exige une cellule unique.")
            if self.cell.index != candidates[0]:
                raise ValueError("La cellule doit correspondre à l'indice candidat.")

    @property
    def binding_id(self) -> str:
        return self.binding.id

    @property
    def production_id(self) -> str:
        return self.binding.production_id

    @property
    def resolved(self) -> bool:
        return self.status is NotebookBindingResolutionStatus.RESOLVED

    @property
    def failed(self) -> bool:
        return not self.resolved

    @property
    def selector(self) -> NotebookCellSelector:
        return self.binding.selector

    @property
    def text_scope(self) -> CellTextScope:
        return self.binding.text_scope


@dataclass(frozen=True, slots=True)
class NotebookBindingResolutionSet:
    """Complete ordered resolutions for one binding plan."""

    binding_plan: NotebookBindingPlan
    resolutions: tuple[NotebookBindingResolution, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.binding_plan, NotebookBindingPlan):
            raise TypeError("Le plan doit être un NotebookBindingPlan.")
        resolutions = tuple(self.resolutions)
        if any(not isinstance(item, NotebookBindingResolution) for item in resolutions):
            raise TypeError("Chaque résultat doit être une NotebookBindingResolution.")
        object.__setattr__(self, "resolutions", resolutions)
        expected_bindings = self.binding_plan.in_evaluation_order
        if len(resolutions) != len(expected_bindings):
            raise ValueError("Une résolution est requise pour chaque rattachement.")
        if any(
            resolution.binding is not binding
            for resolution, binding in zip(resolutions, expected_bindings)
        ):
            raise ValueError("Les résolutions doivent suivre les bindings du plan par identité.")

    def __iter__(self) -> Iterator[NotebookBindingResolution]:
        return iter(self.resolutions)

    def __len__(self) -> int:
        return len(self.resolutions)

    def get(self, binding_id: str) -> NotebookBindingResolution | None:
        for resolution in self.resolutions:
            if resolution.binding_id == binding_id:
                return resolution
        return None

    def for_production(
        self, production_id: str
    ) -> tuple[NotebookBindingResolution, ...]:
        """Return resolutions for one known production."""

        self.binding_plan.for_production(production_id)
        return tuple(
            item for item in self.resolutions if item.production_id == production_id
        )

    def for_status(
        self, status: NotebookBindingResolutionStatus
    ) -> tuple[NotebookBindingResolution, ...]:
        """Return resolutions having one exact status."""

        if not isinstance(status, NotebookBindingResolutionStatus):
            raise TypeError("Le statut doit être un NotebookBindingResolutionStatus.")
        return tuple(item for item in self.resolutions if item.status is status)

    @property
    def resolved(self) -> tuple[NotebookBindingResolution, ...]:
        return self.for_status(NotebookBindingResolutionStatus.RESOLVED)

    @property
    def failures(self) -> tuple[NotebookBindingResolution, ...]:
        return tuple(item for item in self.resolutions if item.failed)

    @property
    def all_resolved(self) -> bool:
        return not self.failures

    @property
    def has_failures(self) -> bool:
        return bool(self.failures)


@dataclass(frozen=True, slots=True)
class _ObservedCell:
    reference: NotebookCellReference
    source: str


def _observe_cells(notebook: NotebookNode) -> tuple[_ObservedCell, ...]:
    if "cells" not in notebook:
        raise ValueError("Le notebook doit contenir une séquence de cellules.")
    cells = notebook["cells"]
    if not isinstance(cells, Sequence) or isinstance(cells, (str, bytes)):
        raise TypeError("Les cellules du notebook doivent former une séquence.")
    observed: list[_ObservedCell] = []
    for index, cell in enumerate(cells):
        if not isinstance(cell, NotebookNode):
            raise TypeError("Chaque cellule doit être un NotebookNode.")
        cell_type = cell.get("cell_type")
        if not isinstance(cell_type, str):
            raise TypeError("Le type de cellule doit être une chaîne.")
        if not cell_type.strip():
            raise ValueError("Le type de cellule ne peut pas être vide.")
        source = cell.get("source")
        if not isinstance(source, str):
            raise TypeError("La source de cellule doit être une chaîne.")
        cell_id = cell.get("id")
        if cell_id is not None and not isinstance(cell_id, str):
            raise TypeError("L'identifiant de cellule doit être une chaîne.")
        metadata = cell.get("metadata")
        if not isinstance(metadata, Mapping):
            raise TypeError("Les métadonnées de cellule doivent être un mapping.")
        tags_value = metadata.get("tags", ())
        if not isinstance(tags_value, (list, tuple)):
            raise TypeError("Les tags de cellule doivent former une liste ou un tuple.")
        if any(not isinstance(tag, str) for tag in tags_value):
            raise TypeError("Chaque tag de cellule doit être une chaîne.")
        reference = NotebookCellReference(index, cell_type, cell_id, tuple(tags_value))
        observed.append(_ObservedCell(reference, source))
    return tuple(observed)


def _matches(cell: _ObservedCell, selector: NotebookCellSelector) -> bool:
    if selector.kind is NotebookCellSelectorKind.CELL_ID:
        return cell.reference.cell_id == selector.value
    if selector.kind is NotebookCellSelectorKind.TAG:
        return selector.value in cell.reference.tags
    return selector.value in cell.source


def _resolve_binding(
    binding: CellProductionBinding,
    cells: tuple[_ObservedCell, ...],
) -> NotebookBindingResolution:
    candidates = tuple(cell for cell in cells if _matches(cell, binding.selector))
    indices = tuple(cell.reference.index for cell in candidates)
    if not candidates:
        return NotebookBindingResolution(
            binding, NotebookBindingResolutionStatus.CELL_NOT_FOUND
        )
    if len(candidates) > 1:
        return NotebookBindingResolution(
            binding, NotebookBindingResolutionStatus.CELL_AMBIGUOUS, indices
        )
    cell = candidates[0]
    if binding.text_scope.kind is CellTextScopeKind.FULL_SOURCE:
        return NotebookBindingResolution(
            binding,
            NotebookBindingResolutionStatus.RESOLVED,
            indices,
            cell.reference,
            cell.source,
            0,
            len(cell.source),
        )
    marker = binding.text_scope.marker
    assert marker is not None
    first_index = cell.source.find(marker)
    if first_index == -1:
        return NotebookBindingResolution(
            binding,
            NotebookBindingResolutionStatus.TEXT_MARKER_NOT_FOUND,
            indices,
            cell.reference,
        )
    second_index = cell.source.find(marker, first_index + 1)
    if second_index != -1:
        return NotebookBindingResolution(
            binding,
            NotebookBindingResolutionStatus.TEXT_MARKER_AMBIGUOUS,
            indices,
            cell.reference,
        )
    start = first_index + len(marker)
    end = len(cell.source)
    return NotebookBindingResolution(
        binding,
        NotebookBindingResolutionStatus.RESOLVED,
        indices,
        cell.reference,
        cell.source[start:end],
        start,
        end,
    )


class NotebookBindingResolver:
    """Resolve one binding plan against an already loaded notebook."""

    def resolve(
        self,
        notebook: NotebookNode,
        binding_plan: NotebookBindingPlan,
    ) -> NotebookBindingResolutionSet:
        if not isinstance(notebook, NotebookNode):
            raise TypeError("Le notebook doit être un NotebookNode déjà chargé.")
        if not isinstance(binding_plan, NotebookBindingPlan):
            raise TypeError("Le plan doit être un NotebookBindingPlan.")
        cells = _observe_cells(notebook)
        resolutions = tuple(
            _resolve_binding(binding, cells)
            for binding in binding_plan.in_evaluation_order
        )
        return NotebookBindingResolutionSet(binding_plan, resolutions)


def resolve_notebook_bindings(
    notebook: NotebookNode,
    binding_plan: NotebookBindingPlan,
) -> NotebookBindingResolutionSet:
    """Delegate resolution to :class:`NotebookBindingResolver`."""

    return NotebookBindingResolver().resolve(notebook, binding_plan)
