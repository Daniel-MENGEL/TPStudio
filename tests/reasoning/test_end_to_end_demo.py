from dataclasses import FrozenInstanceError
import inspect

import pytest

from tpstudio.examples import snell_descartes
from tpstudio.reasoning import (
    ConceptExtractor,
    EndToEndCase,
    format_end_to_end_report,
    run_end_to_end_case,
)


def _components():  # type: ignore[no-untyped-def]
    return (
        ConceptExtractor(snell_descartes.snell_descartes_glossary()),
        snell_descartes.snell_descartes_rules(),
        snell_descartes.snell_descartes_diagnostic_builder(),
    )


def _run(case: EndToEndCase):  # type: ignore[no-untyped-def]
    extractor, rules, builder = _components()
    return run_end_to_end_case(
        case,
        extractor=extractor,
        rules=rules,
        diagnostic_builder=builder,
    )


def test_report_is_immutable_and_facts_are_an_immutable_snapshot() -> None:
    report = _run(snell_descartes.snell_descartes_cases()[0])

    assert isinstance(report.facts, tuple)
    with pytest.raises(FrozenInstanceError):
        report.facts = ()  # type: ignore[misc]


def test_complete_answer_detects_all_concepts_without_diagnostic() -> None:
    report = _run(snell_descartes.snell_descartes_cases()[0])

    assert report.detected_concepts == (
        "snell_descartes",
        "indice_refraction",
        "angle_incidence",
        "angle_refraction",
    )
    assert len(report.diagnostics) == 0
    assert not report.inference_result.triggered


def test_partial_answer_produces_the_two_ordered_angle_diagnostics() -> None:
    case = snell_descartes.snell_descartes_cases()[1]
    report = _run(case)

    assert report.detected_concepts == ("snell_descartes", "indice_refraction")
    assert tuple(item.code for item in report.diagnostics) == (
        "angle_incidence_missing",
        "angle_refraction_missing",
    )
    assert tuple(item.code for item in report.diagnostics) == case.expected_diagnostic_codes


def test_off_topic_answer_only_produces_no_expected_concept() -> None:
    case = snell_descartes.snell_descartes_cases()[2]
    report = _run(case)

    assert report.facts == ()
    assert tuple(item.code for item in report.diagnostics) == (
        "no_expected_concept",
    )


def test_evaluations_and_diagnostics_follow_rule_order() -> None:
    report = _run(snell_descartes.snell_descartes_cases()[1])

    assert tuple(item.rule_id for item in report.inference_result.evaluations) == (
        "SNELL_MISSING_INCIDENCE_ANGLE",
        "SNELL_MISSING_REFRACTION_ANGLE",
        "SNELL_MISSING_REFRACTION_INDEX",
        "SNELL_NO_EXPECTED_CONCEPT",
    )
    assert tuple(item.rule_id for item in report.inference_result.triggered) == (
        "SNELL_MISSING_INCIDENCE_ANGLE",
        "SNELL_MISSING_REFRACTION_ANGLE",
    )
    assert tuple(item.rule_id for item in report.diagnostics) == tuple(
        item.rule_id for item in report.inference_result.triggered
    )


def test_development_render_is_deterministic_and_contains_evidence() -> None:
    report = _run(snell_descartes.snell_descartes_cases()[1])

    first = format_end_to_end_report(report)
    second = format_end_to_end_report(report)

    assert first == second
    assert "Case: partial" in first
    assert "Triggered rules:\n  - SNELL_MISSING_INCIDENCE_ANGLE" in first
    assert "angle_incidence_missing | warning" in first
    assert "evidence: subject=snell_descartes" in first
    assert "excerpt='loi de Snell-Descartes'" in first
    assert "\x1b" not in first


def test_render_without_diagnostic_is_explicit() -> None:
    report = _run(snell_descartes.snell_descartes_cases()[0])
    rendered = format_end_to_end_report(report)

    assert rendered.endswith("Diagnostics:\n  - none")


def test_orchestration_does_not_mutate_injected_objects() -> None:
    case = snell_descartes.snell_descartes_cases()[1]
    extractor, rules, builder = _components()
    rules_before = tuple(rules)
    definitions_before = tuple(builder.registry)

    run_end_to_end_case(
        case,
        extractor=extractor,
        rules=rules,
        diagnostic_builder=builder,
    )

    assert tuple(rules) == rules_before
    assert tuple(builder.registry) == definitions_before
    assert extractor.glossary == snell_descartes.snell_descartes_glossary()


def test_main_demo_flow_never_constructs_facts_manually_or_uses_ai() -> None:
    orchestration_source = inspect.getsource(
        __import__("tpstudio.reasoning.demo", fromlist=["run_end_to_end_case"])
    )
    scenario_source = inspect.getsource(snell_descartes)

    assert "Fact(" not in orchestration_source
    assert "Fact(" not in scenario_source
    assert "openai" not in orchestration_source.lower()
    assert "openai" not in scenario_source.lower()
