"""Teacher-declared bindings between notebook cells and productions."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from .scientific_productions import ScientificProductionPlan


class NotebookCellSelectorKind(str, Enum):
    """Declarative way to identify a future notebook cell."""

    CELL_ID = "cell_id"
    TAG = "tag"
    SOURCE_MARKER = "source_marker"


class NotebookValueTransform(str, Enum):
    """Teacher-declared reduction applied to a notebook value."""

    IDENTITY = "identity"
    MEAN = "mean"


@dataclass(frozen=True, slots=True)
class NotebookCellSelector:
    """Exact selector declared for a future notebook cell lookup."""

    kind: NotebookCellSelectorKind
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, NotebookCellSelectorKind):
            raise TypeError("Le type de sélecteur doit être un NotebookCellSelectorKind.")
        if not isinstance(self.value, str):
            raise TypeError("La valeur du sélecteur doit être une chaîne.")
        if not self.value.strip():
            raise ValueError("La valeur du sélecteur ne peut pas être vide.")


class CellTextScopeKind(str, Enum):
    """Part of a future cell source intended for assessment."""

    FULL_SOURCE = "full_source"
    AFTER_MARKER = "after_marker"


@dataclass(frozen=True, slots=True)
class CellTextScope:
    """Exact textual scope declared for a bound cell."""

    kind: CellTextScopeKind
    marker: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CellTextScopeKind):
            raise TypeError("Le type de portée doit être un CellTextScopeKind.")
        if self.kind is CellTextScopeKind.FULL_SOURCE:
            if self.marker is not None:
                raise ValueError("La source complète ne doit pas définir de marqueur.")
            return
        if not isinstance(self.marker, str):
            raise TypeError("La portée après marqueur exige un marqueur textuel.")
        if not self.marker.strip():
            raise ValueError("Le marqueur de portée ne peut pas être vide.")

    @classmethod
    def full_source(cls) -> CellTextScope:
        """Build a scope covering the complete cell source."""

        return cls(CellTextScopeKind.FULL_SOURCE)

    @classmethod
    def after_marker(cls, marker: str) -> CellTextScope:
        """Build a scope covering text after one literal marker."""

        return cls(CellTextScopeKind.AFTER_MARKER, marker)


@dataclass(frozen=True, slots=True)
class CellProductionBinding:
    """One declared association between a cell selector and a production."""

    id: str
    production_id: str
    selector: NotebookCellSelector
    text_scope: CellTextScope
    description: str = ""
    value_transform: NotebookValueTransform = NotebookValueTransform.IDENTITY

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError("L'identifiant du rattachement doit être une chaîne.")
        if not self.id.strip():
            raise ValueError("L'identifiant du rattachement ne peut pas être vide.")
        if not isinstance(self.production_id, str):
            raise TypeError("L'identifiant de production doit être une chaîne.")
        if not self.production_id.strip():
            raise ValueError("L'identifiant de production ne peut pas être vide.")
        if not isinstance(self.selector, NotebookCellSelector):
            raise TypeError("Le sélecteur doit être un NotebookCellSelector.")
        if not isinstance(self.text_scope, CellTextScope):
            raise TypeError("La portée textuelle doit être un CellTextScope.")
        if not isinstance(self.value_transform, NotebookValueTransform):
            raise TypeError("La transformation de valeur est invalide.")


@dataclass(frozen=True, slots=True)
class NotebookBindingPlan:
    """Ordered declarative cell bindings for one scientific production plan."""

    id: str
    title: str
    production_plan: ScientificProductionPlan
    bindings: tuple[CellProductionBinding, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError("L'identifiant du plan doit être une chaîne.")
        if not self.id.strip():
            raise ValueError("L'identifiant du plan ne peut pas être vide.")
        if not isinstance(self.title, str):
            raise TypeError("Le titre du plan doit être une chaîne.")
        if not self.title.strip():
            raise ValueError("Le titre du plan ne peut pas être vide.")
        if not isinstance(self.production_plan, ScientificProductionPlan):
            raise TypeError("Le plan de productions doit être un ScientificProductionPlan.")

        bindings = tuple(self.bindings)
        if not bindings:
            raise ValueError("Un plan de rattachement ne peut pas être vide.")
        if any(not isinstance(binding, CellProductionBinding) for binding in bindings):
            raise TypeError("Chaque rattachement doit être un CellProductionBinding.")
        object.__setattr__(self, "bindings", bindings)

        binding_ids = [binding.id for binding in bindings]
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("Les identifiants des rattachements doivent être uniques.")
        for binding in bindings:
            if self.production_plan.get(binding.production_id) is None:
                raise ValueError(
                    f"Production inconnue pour le rattachement : {binding.production_id!r}."
                )
        declarations = [
            (binding.production_id, binding.selector, binding.text_scope)
            for binding in bindings
        ]
        if len(declarations) != len(set(declarations)):
            raise ValueError("Une déclaration de rattachement est strictement dupliquée.")

    def __iter__(self) -> Iterator[CellProductionBinding]:
        return iter(self.bindings)

    def __len__(self) -> int:
        return len(self.bindings)

    def get(self, binding_id: str) -> CellProductionBinding | None:
        for binding in self.bindings:
            if binding.id == binding_id:
                return binding
        return None

    def for_production(
        self, production_id: str
    ) -> tuple[CellProductionBinding, ...]:
        """Return declared bindings for one known production."""

        if self.production_plan.get(production_id) is None:
            raise ValueError(f"Production inconnue : {production_id!r}.")
        return tuple(
            binding
            for binding in self.bindings
            if binding.production_id == production_id
        )

    def for_selector(
        self, selector: NotebookCellSelector
    ) -> tuple[CellProductionBinding, ...]:
        """Return declared bindings using one exact selector."""

        if not isinstance(selector, NotebookCellSelector):
            raise TypeError("Le sélecteur doit être un NotebookCellSelector.")
        return tuple(
            binding for binding in self.bindings if binding.selector == selector
        )

    @property
    def in_evaluation_order(self) -> tuple[CellProductionBinding, ...]:
        """Bindings ordered by productions, then by declaration order."""

        return tuple(
            binding
            for production in self.production_plan.evaluation_order
            for binding in self.bindings
            if binding.production_id == production.id
        )
