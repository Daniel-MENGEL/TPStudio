"""Safe, declarative evaluation of derived quantities."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation, Overflow, localcontext
from enum import Enum
import math
from typing import TypeAlias


class RegressionParameterKind(str, Enum):
    """Generic parameter exposed by a resolved regression model."""

    SLOPE = "slope"
    INTERCEPT = "intercept"


@dataclass(frozen=True, slots=True)
class ProductionValue:
    production_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.production_id, str) or not self.production_id.strip():
            raise ValueError("production_id doit être une chaîne non vide.")


@dataclass(frozen=True, slots=True)
class RegressionParameter:
    production_id: str
    parameter: RegressionParameterKind

    def __post_init__(self) -> None:
        if not isinstance(self.production_id, str) or not self.production_id.strip():
            raise ValueError("production_id doit être une chaîne non vide.")
        if not isinstance(self.parameter, RegressionParameterKind):
            raise TypeError("parameter doit être un RegressionParameterKind.")


# Kept as a readable alias for callers that prefer the ``Ref`` suffix.
RegressionParameterRef = RegressionParameter


@dataclass(frozen=True, slots=True)
class TeacherConstant:
    identifier: str
    value: Decimal
    unit: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str) or not self.identifier.strip():
            raise ValueError("identifier doit être une chaîne non vide.")
        value = self.value
        if isinstance(value, bool):
            raise TypeError("value doit être numérique et fini.")
        if not isinstance(value, Decimal):
            try:
                value = Decimal(str(value))
            except Exception as exc:
                raise TypeError("value doit être numérique et fini.") from exc
        if not value.is_finite():
            raise TypeError("value doit être numérique et fini.")
        object.__setattr__(self, "value", value)
        if self.unit is not None and (not isinstance(self.unit, str) or not self.unit.strip()):
            raise ValueError("unit doit être une chaîne non vide ou None.")


DerivedOperand: TypeAlias = ProductionValue | RegressionParameter | TeacherConstant


class DerivedExpression:
    """Marker base class for the closed derived-expression tree."""


def _expression(value: object) -> None:
    # Keep the language deliberately closed: callers cannot smuggle in a
    # Python callable or an arbitrary expression subclass.
    if not isinstance(value, (OperandRef, Constant, _Binary)):
        raise TypeError("Chaque opérande doit appartenir à l'arbre dérivé supporté.")


@dataclass(frozen=True, slots=True)
class OperandRef(DerivedExpression):
    operand: DerivedOperand

    def __post_init__(self) -> None:
        if not isinstance(self.operand, (ProductionValue, RegressionParameter, TeacherConstant)):
            raise TypeError("operand doit être un opérande dérivé.")


@dataclass(frozen=True, slots=True)
class Constant(DerivedExpression):
    value: Decimal

    def __post_init__(self) -> None:
        value = self.value
        if isinstance(value, bool):
            raise TypeError("value doit être numérique et fini.")
        if not isinstance(value, Decimal):
            try:
                value = Decimal(str(value))
            except Exception as exc:
                raise TypeError("value doit être numérique et fini.") from exc
        if not value.is_finite():
            raise TypeError("value doit être numérique et fini.")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class _Binary(DerivedExpression):
    left: DerivedExpression
    right: DerivedExpression

    def __post_init__(self) -> None:
        _expression(self.left)
        _expression(self.right)


class Add(_Binary):
    pass


class Subtract(_Binary):
    pass


class Multiply(_Binary):
    pass


class Divide(_Binary):
    pass


class Power(_Binary):
    pass


def _operand_key(operand: DerivedOperand) -> tuple[str, ...]:
    if isinstance(operand, ProductionValue):
        return ("production", operand.production_id)
    if isinstance(operand, RegressionParameter):
        return ("regression", operand.production_id, operand.parameter.value)
    return ("constant", operand.identifier)


def _operands(expression: DerivedExpression) -> tuple[DerivedOperand, ...]:
    if isinstance(expression, OperandRef):
        return (expression.operand,)
    if isinstance(expression, Constant):
        return ()
    return _operands(expression.left) + _operands(expression.right)


@dataclass(frozen=True, slots=True)
class ExpectedDerivedQuantity:
    production_id: str
    canonical_symbol: str
    sources: tuple[DerivedOperand, ...]
    rule: DerivedExpression
    canonical_unit: str | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.production_id, str) or not self.production_id.strip():
            raise ValueError("production_id doit être une chaîne non vide.")
        if not isinstance(self.canonical_symbol, str) or not self.canonical_symbol.strip():
            raise ValueError("canonical_symbol doit être une chaîne non vide.")
        sources = tuple(self.sources)
        if not sources:
            raise ValueError("Une quantité dérivée exige au moins une source.")
        if any(not isinstance(item, (ProductionValue, RegressionParameter, TeacherConstant)) for item in sources):
            raise TypeError("Chaque source doit être un opérande dérivé.")
        keys = tuple(_operand_key(item) for item in sources)
        if len(keys) != len(set(keys)):
            raise ValueError("Les sources d'une quantité dérivée doivent être uniques.")
        _expression(self.rule)
        referenced = {_operand_key(item) for item in _operands(self.rule)}
        declared = set(keys)
        if not referenced.issubset(declared):
            raise ValueError("La règle référence une source non déclarée.")
        if referenced != declared:
            raise ValueError("Chaque source déclarée doit être utilisée par la règle.")
        if any(isinstance(item, ProductionValue) and item.production_id == self.production_id for item in sources):
            raise ValueError("Une quantité dérivée ne peut pas dépendre directement d'elle-même.")
        if self.canonical_unit is not None and (not isinstance(self.canonical_unit, str) or not self.canonical_unit.strip()):
            raise ValueError("canonical_unit doit être une chaîne non vide ou None.")
        if not isinstance(self.description, str):
            raise TypeError("description doit être une chaîne.")
        object.__setattr__(self, "sources", sources)


@dataclass(frozen=True, slots=True)
class DerivedQuantityExpectationSet:
    """Immutable derived expectations awaiting contextual plan validation."""

    expectations: tuple[ExpectedDerivedQuantity, ...] = ()

    def __post_init__(self) -> None:
        expectations = tuple(self.expectations)
        if any(not isinstance(item, ExpectedDerivedQuantity) for item in expectations):
            raise TypeError(
                "Chaque attendu doit être une ExpectedDerivedQuantity."
            )
        production_ids = [item.production_id for item in expectations]
        if len(production_ids) != len(set(production_ids)):
            raise ValueError(
                "Les identifiants cibles des attentes dérivées doivent être uniques."
            )
        object.__setattr__(self, "expectations", expectations)

    def __iter__(self) -> Iterator[ExpectedDerivedQuantity]:
        return iter(self.expectations)

    def __len__(self) -> int:
        return len(self.expectations)

    def get(self, production_id: str) -> ExpectedDerivedQuantity | None:
        return self.by_production_id(production_id)

    def by_production_id(self, production_id: str) -> ExpectedDerivedQuantity | None:
        return next(
            (item for item in self.expectations if item.production_id == production_id),
            None,
        )


class DerivedQuantityEvaluationStatus(str, Enum):
    CALCULATED = "calculated"
    MISSING_SOURCE = "missing_source"
    NON_NUMERIC_SOURCE = "non_numeric_source"
    DIVISION_BY_ZERO = "division_by_zero"
    INVALID_RESULT = "invalid_result"


@dataclass(frozen=True, slots=True)
class DerivedQuantityEvaluation:
    status: DerivedQuantityEvaluationStatus
    value: Decimal | None
    diagnostics: tuple[str, ...]
    sources_used: tuple[tuple[str, ...], ...]


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        try:
            result = Decimal(str(value))
        except Exception:
            return None
        return result if result.is_finite() else None
    return None


def evaluate_derived_quantity(
    expectation: ExpectedDerivedQuantity,
    resolved_sources: Mapping[DerivedOperand, object],
) -> DerivedQuantityEvaluation:
    """Evaluate a validated closed expression without executing source text."""

    if not isinstance(expectation, ExpectedDerivedQuantity):
        raise TypeError("expectation doit être une ExpectedDerivedQuantity.")
    used = tuple(_operand_key(item) for item in expectation.sources)

    def evaluate(expression: DerivedExpression) -> tuple[Decimal | None, str | None]:
        if isinstance(expression, Constant):
            return expression.value, None
        if isinstance(expression, OperandRef):
            if isinstance(expression.operand, TeacherConstant):
                return expression.operand.value, None
            if expression.operand not in resolved_sources:
                return None, f"source manquante: {_operand_key(expression.operand)}"
            value = _decimal(resolved_sources[expression.operand])
            if value is None:
                return None, f"source non numérique: {_operand_key(expression.operand)}"
            return value, None
        left, error = evaluate(expression.left)
        if error:
            return None, error
        right, error = evaluate(expression.right)
        if error:
            return None, error
        assert left is not None and right is not None
        try:
            with localcontext() as context:
                context.traps[DivisionByZero] = True
                context.traps[InvalidOperation] = True
                if isinstance(expression, Add):
                    return left + right, None
                if isinstance(expression, Subtract):
                    return left - right, None
                if isinstance(expression, Multiply):
                    return left * right, None
                if isinstance(expression, Divide):
                    return left / right, None
                if isinstance(expression, Power):
                    return left ** right, None
        except DivisionByZero:
            return None, "division par zéro"
        except (InvalidOperation, Overflow, OverflowError, ValueError):
            return None, "opération numérique invalide"
        return None, "opération dérivée non supportée"

    value, error = evaluate(expectation.rule)
    if error is not None:
        status = (
            DerivedQuantityEvaluationStatus.DIVISION_BY_ZERO
            if error == "division par zéro"
            else DerivedQuantityEvaluationStatus.MISSING_SOURCE
            if error.startswith("source manquante")
            else DerivedQuantityEvaluationStatus.NON_NUMERIC_SOURCE
            if error.startswith("source non numérique")
            else DerivedQuantityEvaluationStatus.INVALID_RESULT
        )
        return DerivedQuantityEvaluation(status, None, (error,), used)
    if value is None or not value.is_finite():
        return DerivedQuantityEvaluation(
            DerivedQuantityEvaluationStatus.INVALID_RESULT,
            None,
            ("résultat non fini",),
            used,
        )
    return DerivedQuantityEvaluation(
        DerivedQuantityEvaluationStatus.CALCULATED,
        value,
        (),
        used,
    )
