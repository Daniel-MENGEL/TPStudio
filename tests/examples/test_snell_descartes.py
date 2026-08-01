import pytest

from tpstudio.examples.snell_descartes import (
    run_snell_descartes_demo,
    snell_descartes_expectations,
)
from tpstudio.reasoning import match_declared_relations


def test_canonical_latex_expression_is_found_inside_delimiters() -> None:
    text = r"La relation est $n_1 \sin(i_1) = n_2 \sin(i_2)$."

    detection = match_declared_relations(text, snell_descartes_expectations()).found[0]
    match = detection.first_match

    assert match is not None
    assert match.is_canonical
    assert match.matched_text == r"n_1 \sin(i_1) = n_2 \sin(i_2)"
    assert text[match.start : match.end] == match.matched_text


def test_declared_ascii_variant_is_found() -> None:
    detections = match_declared_relations(
        "On utilise n1 sin(i1) = n2 sin(i2).",
        snell_descartes_expectations(),
    )

    match = detections.found[0].first_match
    assert match is not None
    assert match.declared_expression == "n1 sin(i1) = n2 sin(i2)"
    assert not match.is_canonical


def test_explicitly_declared_reversed_unicode_variant_is_found() -> None:
    text = "n₂ sin(i₂) = n₁ sin(i₁)"

    match = match_declared_relations(
        text, snell_descartes_expectations()
    ).found[0].first_match

    assert match is not None
    assert match.matched_text == text
    assert not match.is_canonical


@pytest.mark.parametrize(
    "text",
    (
        "La lumière change de direction entre les deux milieux.",
        "n1*sin(i1)=n2*sin(i2)",
    ),
)
def test_absent_or_merely_similar_relation_is_not_found(text: str) -> None:
    detections = match_declared_relations(text, snell_descartes_expectations())

    assert not detections.found
    assert [item.relation_id for item in detections.missing] == [
        "snell_descartes_relation"
    ]


def test_existing_a66_5_demo_output_is_unchanged() -> None:
    reports = run_snell_descartes_demo()

    assert [report.case.case_id for report in reports] == [
        "complete",
        "partial",
        "off-topic",
    ]
    assert [item.code for item in reports[1].diagnostics] == [
        "angle_incidence_missing",
        "angle_refraction_missing",
    ]
    assert reports[0].detected_concepts == (
        "snell_descartes",
        "indice_refraction",
        "angle_incidence",
        "angle_refraction",
    )
