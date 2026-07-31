import pytest

from tpstudio.glossary.models import Glossary, ScientificTerm
from tpstudio.glossary.registry import GlossaryRegistry


def test_registry_registers_gets_and_composes_glossaries() -> None:
    optics = Glossary("optics", "Optique", (ScientificTerm("angle", "angle", "quantity"),))
    methods = Glossary("methods", "Méthodes", (ScientificTerm("mesure", "mesure", "method"),))
    registry = GlossaryRegistry()
    registry.register(optics)
    registry.register(methods)

    combined = registry.compose(("optics", "methods"), id="all", title="Tous")

    assert registry.get("optics") == optics
    assert [term.id for term in combined.terms] == ["angle", "mesure"]


def test_registry_rejects_unknown_or_ambiguous_composition() -> None:
    registry = GlossaryRegistry()

    with pytest.raises(KeyError):
        registry.compose(("missing",), id="all", title="Tous")

    registry.register(Glossary("one", "One", (ScientificTerm("angle", "angle", "quantity"),)))
    registry.register(Glossary("two", "Two", (ScientificTerm("angle", "angle", "quantity"),)))
    with pytest.raises(ValueError):
        registry.compose(("one", "two"), id="all", title="Tous")
