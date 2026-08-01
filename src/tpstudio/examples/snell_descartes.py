"""Observable end-to-end demo for Snell-Descartes concept mentions."""

from __future__ import annotations

from tpstudio.expectations import (
    ExpectedConclusion,
    ExpectedRelation,
    ExpectationSet,
)
from tpstudio.glossary import Glossary, ScientificTerm
from tpstudio.reasoning import (
    AllOf,
    AnyOf,
    ConceptExtractor,
    DiagnosticBuilder,
    DiagnosticCategory,
    DiagnosticDefinition,
    DiagnosticRegistry,
    DiagnosticSeverity,
    EndToEndCase,
    EndToEndReport,
    Not,
    Rule,
    RuleConclusion,
    RuleSet,
    SubjectExists,
    format_end_to_end_report,
    run_end_to_end_case,
)


def snell_descartes_expectations() -> ExpectationSet:
    """Return teacher references, not inputs to the A66.5 demo pipeline."""

    return ExpectationSet(
        id="snell_descartes_answer",
        title="Attendus sur la loi de Snell-Descartes",
        relations=(
            ExpectedRelation(
                id="snell_descartes_relation",
                label="Relation de Snell-Descartes",
                canonical_expression=r"n_1 \sin(i_1) = n_2 \sin(i_2)",
                accepted_expressions=(
                    "n1 sin(i1) = n2 sin(i2)",
                    "n₂ sin(i₂) = n₁ sin(i₁)",
                ),
            ),
        ),
        conclusions=(
            ExpectedConclusion(
                id="snell_variables_conclusion",
                label="Grandeurs reliées par la loi",
                canonical_statement=(
                    "La loi relie les indices de réfraction aux angles "
                    "d’incidence et de réfraction."
                ),
            ),
        ),
        description="Références déclarées par le professeur pour la réponse.",
    )


def snell_descartes_glossary() -> Glossary:
    return Glossary(
        "snell-descartes-demo",
        "Démonstration Snell-Descartes",
        (
            ScientificTerm(
                "snell_descartes",
                "loi de Snell-Descartes",
                "phenomenon",
                aliases=("Snell-Descartes", "loi de Snell", "loi de Descartes"),
            ),
            ScientificTerm(
                "indice_refraction",
                "indice de réfraction",
                "quantity",
                aliases=("indices de réfraction", "indice optique"),
            ),
            ScientificTerm(
                "angle_incidence",
                "angle d'incidence",
                "quantity",
                aliases=("angle incident",),
            ),
            ScientificTerm(
                "angle_refraction",
                "angle de réfraction",
                "quantity",
                aliases=("angle réfracté",),
            ),
        ),
    )


def snell_descartes_rules() -> RuleSet:
    law_mentioned = SubjectExists("snell_descartes")
    expected_concept = AnyOf(
        SubjectExists("snell_descartes"),
        SubjectExists("indice_refraction"),
        SubjectExists("angle_incidence"),
        SubjectExists("angle_refraction"),
    )
    return RuleSet(
        (
            Rule(
                "SNELL_MISSING_INCIDENCE_ANGLE",
                AllOf(law_mentioned, Not(SubjectExists("angle_incidence"))),
                RuleConclusion("angle_incidence_missing"),
                label="Angle d'incidence absent",
            ),
            Rule(
                "SNELL_MISSING_REFRACTION_ANGLE",
                AllOf(law_mentioned, Not(SubjectExists("angle_refraction"))),
                RuleConclusion("angle_refraction_missing"),
                label="Angle de réfraction absent",
            ),
            Rule(
                "SNELL_MISSING_REFRACTION_INDEX",
                AllOf(law_mentioned, Not(SubjectExists("indice_refraction"))),
                RuleConclusion("refractive_index_missing"),
                label="Indice de réfraction absent",
            ),
            Rule(
                "SNELL_NO_EXPECTED_CONCEPT",
                Not(expected_concept),
                RuleConclusion("no_expected_concept"),
                label="Aucun concept attendu détecté",
            ),
        )
    )


def snell_descartes_diagnostic_builder() -> DiagnosticBuilder:
    definitions = (
        DiagnosticDefinition(
            "angle_incidence_missing",
            "angle_incidence_missing",
            DiagnosticCategory.MISSING_ELEMENT,
            DiagnosticSeverity.WARNING,
            "diagnostic.snell.angle_incidence_missing",
            subject="angle_incidence",
        ),
        DiagnosticDefinition(
            "angle_refraction_missing",
            "angle_refraction_missing",
            DiagnosticCategory.MISSING_ELEMENT,
            DiagnosticSeverity.WARNING,
            "diagnostic.snell.angle_refraction_missing",
            subject="angle_refraction",
        ),
        DiagnosticDefinition(
            "refractive_index_missing",
            "refractive_index_missing",
            DiagnosticCategory.MISSING_ELEMENT,
            DiagnosticSeverity.WARNING,
            "diagnostic.snell.refractive_index_missing",
            subject="indice_refraction",
        ),
        DiagnosticDefinition(
            "no_expected_concept",
            "no_expected_concept",
            DiagnosticCategory.MISSING_ELEMENT,
            DiagnosticSeverity.WARNING,
            "diagnostic.snell.no_expected_concept",
        ),
    )
    return DiagnosticBuilder(DiagnosticRegistry(definitions))


def snell_descartes_cases() -> tuple[EndToEndCase, ...]:
    return (
        EndToEndCase(
            "complete",
            "La loi de Snell-Descartes relie l'indice de réfraction, "
            "l'angle d'incidence et l'angle de réfraction.",
            "Tous les concepts attendus sont mentionnés.",
        ),
        EndToEndCase(
            "partial",
            "La loi de Snell-Descartes utilise les indices de réfraction.",
            "La loi et les indices sont présents, mais pas les angles.",
            ("angle_incidence_missing", "angle_refraction_missing"),
        ),
        EndToEndCase(
            "off-topic",
            "Le pendule oscille pendant plusieurs secondes.",
            "Aucun concept du scénario optique n'est présent.",
            ("no_expected_concept",),
        ),
    )


def run_snell_descartes_demo() -> tuple[EndToEndReport, ...]:
    extractor = ConceptExtractor(snell_descartes_glossary())
    rules = snell_descartes_rules()
    builder = snell_descartes_diagnostic_builder()
    return tuple(
        run_end_to_end_case(
            case,
            extractor=extractor,
            rules=rules,
            diagnostic_builder=builder,
        )
        for case in snell_descartes_cases()
    )


def main() -> None:
    rendered = (
        format_end_to_end_report(report) for report in run_snell_descartes_demo()
    )
    print("\n\n".join(rendered))


if __name__ == "__main__":
    main()
