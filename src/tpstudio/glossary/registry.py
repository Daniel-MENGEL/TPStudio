"""Selection and composition helpers for glossaries."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Glossary, ScientificTerm


@dataclass(slots=True)
class GlossaryRegistry:
    """A small in-memory registry keyed by glossary identifier."""

    glossaries: dict[str, Glossary] = field(default_factory=dict)

    def register(self, glossary: Glossary) -> None:
        self.glossaries[glossary.id] = glossary

    def get(self, glossary_id: str) -> Glossary | None:
        return self.glossaries.get(glossary_id)

    def compose(self, glossary_ids: tuple[str, ...], *, id: str, title: str) -> Glossary:
        """Combine registered glossaries, rejecting ambiguous term identifiers."""

        terms: list[ScientificTerm] = []
        seen_ids: set[str] = set()
        for glossary_id in glossary_ids:
            glossary = self.get(glossary_id)
            if glossary is None:
                raise KeyError(f"Glossaire inconnu : {glossary_id}")
            for term in glossary.terms:
                if term.id in seen_ids:
                    raise ValueError(f"Identifiant de terme dupliqué : {term.id}")
                seen_ids.add(term.id)
                terms.append(term)
        return Glossary(id=id, title=title, terms=tuple(terms))
