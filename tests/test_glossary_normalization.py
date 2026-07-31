from tpstudio.glossary.normalization import normalize_scientific_text


def test_normalization_is_case_and_accent_insensitive() -> None:
    assert normalize_scientific_text(" RéFRACTION  expérimentale ") == "refraction experimentale"


def test_normalization_expands_ligatures_and_collapses_whitespace() -> None:
    assert normalize_scientific_text("Cœur\n  optique") == "coeur optique"


def test_normalization_preserves_original_offsets() -> None:
    from tpstudio.glossary.normalization import normalize_scientific_text_with_offsets

    source = "  Cœur\n  optique  "
    normalized = normalize_scientific_text_with_offsets(source)

    assert normalized.text == "coeur optique"
    assert normalized.original_span(0, 5) == (2, 6)
    assert source[slice(*normalized.original_span(6, 13))] == "optique"
