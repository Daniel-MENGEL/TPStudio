"""Declarative scientific expectations supplied by a teacher."""

from __future__ import annotations

from dataclasses import dataclass


def _declared_variants(canonical: str, variants: tuple[str, ...]) -> tuple[str, ...]:
    """Deduplicate exact declarations without normalizing their content."""

    return tuple(dict.fromkeys((canonical, *variants)))


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"Le champ {field_name!r} ne peut pas être vide.")


@dataclass(frozen=True, slots=True)
class ExpectedRelation:
    """One mathematical relation explicitly declared by the teacher."""

    id: str
    label: str
    canonical_expression: str
    accepted_expressions: tuple[str, ...] = ()
    description: str = ""
    required: bool = True

    def __post_init__(self) -> None:
        _require_text(self.id, "id")
        _require_text(self.label, "label")
        _require_text(self.canonical_expression, "canonical_expression")
        object.__setattr__(
            self, "accepted_expressions", tuple(self.accepted_expressions)
        )
        if any(not expression.strip() for expression in self.accepted_expressions):
            raise ValueError("Une expression acceptée ne peut pas être vide.")

    @property
    def expressions(self) -> tuple[str, ...]:
        """Canonical expression then exact declared variants, deduplicated."""

        return _declared_variants(
            self.canonical_expression,
            self.accepted_expressions,
        )


@dataclass(frozen=True, slots=True)
class ExpectedConclusion:
    """One semantic conclusion explicitly declared by the teacher."""

    id: str
    label: str
    canonical_statement: str
    accepted_statements: tuple[str, ...] = ()
    description: str = ""
    required: bool = True

    def __post_init__(self) -> None:
        _require_text(self.id, "id")
        _require_text(self.label, "label")
        _require_text(self.canonical_statement, "canonical_statement")
        object.__setattr__(self, "accepted_statements", tuple(self.accepted_statements))
        if any(not statement.strip() for statement in self.accepted_statements):
            raise ValueError("Une formulation acceptée ne peut pas être vide.")

    @property
    def statements(self) -> tuple[str, ...]:
        """Canonical statement then exact declared variants, deduplicated."""

        return _declared_variants(
            self.canonical_statement,
            self.accepted_statements,
        )


Expectation = ExpectedRelation | ExpectedConclusion


@dataclass(frozen=True, slots=True)
class ExpectationSet:
    """Ordered expectations for one future pedagogical scope."""

    id: str
    title: str
    relations: tuple[ExpectedRelation, ...] = ()
    conclusions: tuple[ExpectedConclusion, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        _require_text(self.id, "id")
        _require_text(self.title, "title")
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "conclusions", tuple(self.conclusions))

        relation_ids = [relation.id for relation in self.relations]
        conclusion_ids = [conclusion.id for conclusion in self.conclusions]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("Les identifiants des relations doivent être uniques.")
        if len(conclusion_ids) != len(set(conclusion_ids)):
            raise ValueError("Les identifiants des conclusions doivent être uniques.")
        shared_ids = set(relation_ids).intersection(conclusion_ids)
        if shared_ids:
            raise ValueError(
                "Une relation et une conclusion ne peuvent pas partager un "
                "identifiant."
            )

    def relation_by_id(self, relation_id: str) -> ExpectedRelation | None:
        for relation in self.relations:
            if relation.id == relation_id:
                return relation
        return None

    def conclusion_by_id(self, conclusion_id: str) -> ExpectedConclusion | None:
        for conclusion in self.conclusions:
            if conclusion.id == conclusion_id:
                return conclusion
        return None

    def expectation_by_id(self, expectation_id: str) -> Expectation | None:
        relation = self.relation_by_id(expectation_id)
        if relation is not None:
            return relation
        return self.conclusion_by_id(expectation_id)
