import pytest

from tpstudio.glossary.defaults import default_scientific_glossary
from tpstudio.glossary.matcher import matched_term_ids


def test_default_glossary_covers_existing_optics_vocabulary() -> None:
    glossary = default_scientific_glossary()
    found = matched_term_ids(
        "L'indice du plexiglas est obtenu avec les angles de réfraction selon Snell-Descartes.",
        glossary,
    )

    assert {"indice", "plexiglas", "angle", "refraction", "snell-descartes"} <= found


def test_default_glossary_has_unique_term_identifiers() -> None:
    glossary = default_scientific_glossary()

    assert len({term.id for term in glossary.terms}) == len(glossary.terms)


@pytest.mark.parametrize(
    ("text", "term_id"),
    [
        ("indice", "indice"),
        ("plexiglas", "plexiglas"),
        ("réfraction", "refraction"),
        ("refraction", "refraction"),
        ("Snell", "snell-descartes"),
        ("Descartes", "snell-descartes"),
        ("angles", "angle"),
        ("pente", "pente"),
        ("incertitudes", "incertitude"),
        ("écart normalisé", "ecart-normalise"),
        ("sinus", "sinus"),
        ("mesures", "mesure"),
        ("expérimentale", "experimental"),
        ("loi", "loi"),
        ("droite", "droite"),
        ("alignés", "droite"),
    ],
)
def test_default_glossary_preserves_intended_legacy_vocabulary(
    text: str,
    term_id: str,
) -> None:
    assert term_id in matched_term_ids(text, default_scientific_glossary())


def test_default_glossary_drops_accidental_substring_matches() -> None:
    glossary = default_scientific_glossary()

    assert matched_term_ids("Un angleur lointain.", glossary) == set()
