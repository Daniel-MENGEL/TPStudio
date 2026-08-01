import inspect

from tpstudio.examples import snell_descartes
from tpstudio.expectations import ExpectedConclusion, ExpectedRelation


def test_snell_expectations_declare_one_relation_and_one_conclusion() -> None:
    expectations = snell_descartes.snell_descartes_expectations()

    assert expectations.id == "snell_descartes_answer"
    assert len(expectations.relations) == 1
    assert len(expectations.conclusions) == 1
    assert isinstance(expectations.relations[0], ExpectedRelation)
    assert isinstance(expectations.conclusions[0], ExpectedConclusion)
    assert expectations.relations[0].canonical_expression == (
        r"n_1 \sin(i_1) = n_2 \sin(i_2)"
    )


def test_expectations_are_not_connected_to_the_existing_demo_flow() -> None:
    source = inspect.getsource(snell_descartes.run_snell_descartes_demo)

    assert "snell_descartes_expectations" not in source
    reports = snell_descartes.run_snell_descartes_demo()
    assert tuple(report.case.case_id for report in reports) == (
        "complete",
        "partial",
        "off-topic",
    )
    assert tuple(item.code for item in reports[1].diagnostics) == (
        "angle_incidence_missing",
        "angle_refraction_missing",
    )


def test_snell_expectations_never_construct_facts() -> None:
    source = inspect.getsource(snell_descartes.snell_descartes_expectations)

    assert "Fact(" not in source
