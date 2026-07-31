"""Deterministic conversion of glossary matches into facts."""

from __future__ import annotations

from tpstudio.glossary import Glossary, default_scientific_glossary, match_terms

from .enums import FactKind
from .evidence import Evidence
from .fact_set import FactSet
from .facts import Fact


class ConceptExtractor:
    """Extract concept mentions using only a scientific glossary."""

    def __init__(self, glossary: Glossary | None = None) -> None:
        self._glossary = glossary or default_scientific_glossary()

    @property
    def glossary(self) -> Glossary:
        return self._glossary

    def extract(self, text: str) -> FactSet:
        """Return one concept-mention fact per glossary concept."""

        facts = FactSet()
        for match in match_terms(text, self._glossary):
            evidence = Evidence(
                source_text=text,
                start=match.start,
                end=match.end,
                matched_term=match.term.id,
            )
            facts.add(
                Fact(
                    id=(
                        f"{FactKind.CONCEPT_MENTION.value}:"
                        f"{match.term.id}:{match.start}:{match.end}"
                    ),
                    kind=FactKind.CONCEPT_MENTION,
                    subject=match.term.id,
                    predicate="mentioned",
                    confidence=1.0,
                    evidence=evidence,
                )
            )
        return facts


def extract_concepts(text: str, glossary: Glossary | None = None) -> FactSet:
    """Convenience function for one-off concept extraction."""

    return ConceptExtractor(glossary).extract(text)


# Generic names kept alongside the precise A63 names so callers do not have to
# change vocabulary when later extractors learn to emit additional fact kinds.
FactExtractor = ConceptExtractor
extract_facts = extract_concepts
