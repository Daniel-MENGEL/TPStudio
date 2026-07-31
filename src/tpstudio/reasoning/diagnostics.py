"""Language-independent pedagogical diagnostics and their registry."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import Enum
from typing import overload

from .facts import Fact
from .rules import RuleConclusion, StructuredData


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticCategory(str, Enum):
    MISSING_ELEMENT = "missing_element"
    INCORRECT_ELEMENT = "incorrect_element"
    INCONSISTENCY = "inconsistency"
    METHOD = "method"
    JUSTIFICATION = "justification"
    PRECISION = "precision"
    POSITIVE = "positive"
    OTHER = "other"


@dataclass(frozen=True, slots=True, init=False)
class Diagnostic:
    """One structured pedagogical interpretation of a rule conclusion."""

    code: str
    category: DiagnosticCategory
    severity: DiagnosticSeverity
    message_key: str
    rule_id: str
    conclusion: RuleConclusion
    evidence: tuple[Fact, ...]
    subject: str | None
    metadata: StructuredData
    conclusion_data: StructuredData

    def __init__(
        self,
        code: str,
        category: DiagnosticCategory | str,
        severity: DiagnosticSeverity | str | None = None,
        message_key: str | object | None = None,
        rule_id: str | None = None,
        conclusion: RuleConclusion | None = None,
        evidence: Iterable[Fact] = (),
        subject: str | None = None,
        metadata: StructuredData = (),
        conclusion_data: StructuredData | None = None,
    ) -> None:
        # Compatibility with ``Diagnostic(code, message, rule_id, location)``,
        # the pre-A66 placeholder that was never used for inference output.
        if (
            isinstance(category, str)
            and not isinstance(category, DiagnosticCategory)
            and isinstance(severity, str)
            and rule_id is None
        ):
            legacy_rule_id = severity
            category = DiagnosticCategory.OTHER
            severity = DiagnosticSeverity.INFO
            message_key = "legacy.diagnostic"
            rule_id = legacy_rule_id
            conclusion = RuleConclusion(code=f"legacy:{code}")

        if not isinstance(category, DiagnosticCategory):
            raise TypeError("La catégorie doit être une DiagnosticCategory.")
        if not isinstance(severity, DiagnosticSeverity):
            raise TypeError("La gravité doit être une DiagnosticSeverity.")
        if not isinstance(message_key, str) or not message_key:
            raise ValueError("La clé de message ne peut pas être vide.")
        if not rule_id:
            raise ValueError("L'identifiant de règle ne peut pas être vide.")
        if conclusion is None:
            raise ValueError("La conclusion source est obligatoire.")
        if not code:
            raise ValueError("Le code du diagnostic ne peut pas être vide.")

        object.__setattr__(self, "code", code)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "message_key", message_key)
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "conclusion", conclusion)
        object.__setattr__(self, "evidence", tuple(evidence))
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "metadata", tuple(metadata))
        object.__setattr__(
            self,
            "conclusion_data",
            tuple(conclusion.data if conclusion_data is None else conclusion_data),
        )


@dataclass(frozen=True, slots=True)
class DiagnosticSet:
    """An immutable, ordered collection that deliberately keeps duplicates."""

    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    def __iter__(self) -> Iterator[Diagnostic]:
        return iter(self.diagnostics)

    def __len__(self) -> int:
        return len(self.diagnostics)

    def __bool__(self) -> bool:
        return bool(self.diagnostics)

    @overload
    def __getitem__(self, index: int) -> Diagnostic: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Diagnostic, ...]: ...

    def __getitem__(self, index: int | slice) -> Diagnostic | tuple[Diagnostic, ...]:
        return self.diagnostics[index]

    def by_severity(self, severity: DiagnosticSeverity) -> DiagnosticSet:
        return DiagnosticSet(
            tuple(item for item in self if item.severity is severity)
        )

    def by_category(self, category: DiagnosticCategory) -> DiagnosticSet:
        return DiagnosticSet(
            tuple(item for item in self if item.category is category)
        )

    def by_code(self, code: str) -> DiagnosticSet:
        return DiagnosticSet(tuple(item for item in self if item.code == code))

    def by_rule_id(self, rule_id: str) -> DiagnosticSet:
        return DiagnosticSet(
            tuple(item for item in self if item.rule_id == rule_id)
        )


@dataclass(frozen=True, slots=True)
class DiagnosticDefinition:
    """Static mapping from one conclusion code to a diagnostic shape."""

    conclusion_code: str
    diagnostic_code: str
    category: DiagnosticCategory
    severity: DiagnosticSeverity
    message_key: str
    subject: str | None = None
    metadata: StructuredData = ()

    def __post_init__(self) -> None:
        if not self.conclusion_code or not self.diagnostic_code:
            raise ValueError("Les codes de définition ne peuvent pas être vides.")
        if not self.message_key:
            raise ValueError("La clé de message ne peut pas être vide.")
        if not isinstance(self.category, DiagnosticCategory):
            raise TypeError("La catégorie doit être une DiagnosticCategory.")
        if not isinstance(self.severity, DiagnosticSeverity):
            raise TypeError("La gravité doit être une DiagnosticSeverity.")
        object.__setattr__(self, "metadata", tuple(self.metadata))


@dataclass(frozen=True, slots=True)
class DiagnosticRegistry:
    """An immutable registry with one unambiguous definition per code."""

    definitions: tuple[DiagnosticDefinition, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "definitions", tuple(self.definitions))
        codes = [definition.conclusion_code for definition in self.definitions]
        if len(codes) != len(set(codes)):
            raise ValueError(
                "Une seule définition est autorisée par code de conclusion."
            )

    def __iter__(self) -> Iterator[DiagnosticDefinition]:
        return iter(self.definitions)

    def __len__(self) -> int:
        return len(self.definitions)

    def get(self, conclusion_code: str) -> DiagnosticDefinition | None:
        for definition in self.definitions:
            if definition.conclusion_code == conclusion_code:
                return definition
        return None


class UnknownDiagnosticDefinitionError(LookupError):
    """Raised when no diagnostic definition maps a produced conclusion."""

    def __init__(self, conclusion_code: str) -> None:
        self.conclusion_code = conclusion_code
        super().__init__(
            f"Aucune définition de diagnostic pour la conclusion "
            f"{conclusion_code!r}."
        )
