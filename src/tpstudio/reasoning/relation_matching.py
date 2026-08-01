"""Strictly literal matching of teacher-declared scientific relations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from tpstudio.expectations import ExpectedRelation, ExpectationSet


@dataclass(frozen=True, slots=True)
class RelationMatch:
    """One exact occurrence of a declared expression in student text."""

    relation_id: str
    declared_expression: str
    matched_text: str
    start: int
    end: int
    is_canonical: bool

    def __post_init__(self) -> None:
        if not self.relation_id.strip():
            raise ValueError("L'identifiant de relation ne peut pas être vide.")
        if not self.declared_expression.strip():
            raise ValueError("L'expression déclarée ne peut pas être vide.")
        if not self.matched_text.strip():
            raise ValueError("Le fragment reconnu ne peut pas être vide.")
        if self.start < 0:
            raise ValueError("La position de début ne peut pas être négative.")
        if self.end <= self.start:
            raise ValueError("La position de fin doit suivre le début.")
        if self.end - self.start != len(self.matched_text):
            raise ValueError("Les positions ne correspondent pas au fragment reconnu.")
        if self.matched_text != self.declared_expression:
            raise ValueError(
                "Une correspondance littérale doit être identique à "
                "l'expression déclarée."
            )


@dataclass(frozen=True, slots=True)
class RelationDetection:
    """All literal occurrences found for one expected relation."""

    relation: ExpectedRelation
    matches: tuple[RelationMatch, ...] = ()

    def __post_init__(self) -> None:
        expressions = self.relation.expressions
        expression_order = {
            expression: index for index, expression in enumerate(expressions)
        }
        unique_by_identity: dict[tuple[str, int, int, str], RelationMatch] = {}
        for match in self.matches:
            if match.relation_id != self.relation.id:
                raise ValueError(
                    "Chaque correspondance doit référencer la relation détectée."
                )
            if match.declared_expression not in expression_order:
                raise ValueError(
                    "Chaque correspondance doit utiliser une expression déclarée."
                )
            expected_canonical = (
                match.declared_expression == self.relation.canonical_expression
            )
            if match.is_canonical != expected_canonical:
                raise ValueError(
                    "Le statut canonique ne correspond pas à l'expression déclarée."
                )
            identity = (
                match.relation_id,
                match.start,
                match.end,
                match.declared_expression,
            )
            unique_by_identity.setdefault(identity, match)
        unique_matches = tuple(
            sorted(
                unique_by_identity.values(),
                key=lambda match: (
                    match.start,
                    expression_order[match.declared_expression],
                    match.end,
                ),
            )
        )
        object.__setattr__(self, "matches", unique_matches)

    @property
    def relation_id(self) -> str:
        return self.relation.id

    @property
    def found(self) -> bool:
        return bool(self.matches)

    @property
    def first_match(self) -> RelationMatch | None:
        return self.matches[0] if self.matches else None


@dataclass(frozen=True, slots=True)
class RelationDetectionSet:
    """Ordered detections for every relation in one expectation set."""

    expectation_set_id: str
    detections: tuple[RelationDetection, ...]

    def __post_init__(self) -> None:
        if not self.expectation_set_id.strip():
            raise ValueError("L'identifiant du jeu d'attendus ne peut pas être vide.")
        object.__setattr__(self, "detections", tuple(self.detections))
        relation_ids = [detection.relation_id for detection in self.detections]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("Les identifiants des relations doivent être uniques.")

    def __iter__(self) -> Iterator[RelationDetection]:
        return iter(self.detections)

    def __len__(self) -> int:
        return len(self.detections)

    def get(self, relation_id: str) -> RelationDetection | None:
        for detection in self.detections:
            if detection.relation_id == relation_id:
                return detection
        return None

    relation_detection_by_id = get

    @property
    def found(self) -> tuple[RelationDetection, ...]:
        return tuple(detection for detection in self if detection.found)

    @property
    def missing(self) -> tuple[RelationDetection, ...]:
        return tuple(detection for detection in self if not detection.found)


class LiteralRelationMatcher:
    """Find exact declared strings without normalization or interpretation."""

    def match(
        self,
        text: str,
        expectations: ExpectationSet,
    ) -> RelationDetectionSet:
        detections: list[RelationDetection] = []
        for relation in expectations.relations:
            candidates: list[tuple[int, int, RelationMatch]] = []
            for expression_order, expression in enumerate(relation.expressions):
                search_start = 0
                while True:
                    start = text.find(expression, search_start)
                    if start < 0:
                        break
                    end = start + len(expression)
                    candidates.append(
                        (
                            start,
                            expression_order,
                            RelationMatch(
                                relation_id=relation.id,
                                declared_expression=expression,
                                matched_text=text[start:end],
                                start=start,
                                end=end,
                                is_canonical=(
                                    expression == relation.canonical_expression
                                ),
                            ),
                        )
                    )
                    search_start = start + 1

            candidates.sort(key=lambda item: (item[0], item[1]))
            seen: set[tuple[str, int, int, str]] = set()
            matches: list[RelationMatch] = []
            for _, _, match in candidates:
                identity = (
                    match.relation_id,
                    match.start,
                    match.end,
                    match.declared_expression,
                )
                if identity not in seen:
                    seen.add(identity)
                    matches.append(match)
            detections.append(RelationDetection(relation, tuple(matches)))

        return RelationDetectionSet(expectations.id, tuple(detections))


def match_declared_relations(
    text: str,
    expectations: ExpectationSet,
) -> RelationDetectionSet:
    """Convenience wrapper around :class:`LiteralRelationMatcher`."""

    return LiteralRelationMatcher().match(text, expectations)
