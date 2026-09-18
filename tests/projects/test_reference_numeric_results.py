from decimal import Decimal
from pathlib import Path
import re

import nbformat
import pytest

from tpstudio.orchestration import NotebookCopySource, analyze_copy
from tpstudio.projects import (
    focometry_teacher_project,
    prism_goniometer_teacher_project,
    snells_laws_teacher_project,
    thin_lens_teacher_project,
)


REFERENCE_DIR = Path(__file__).parents[2] / "reference-notebooks"


def test_active_reference_notebooks_do_not_expose_historical_tpstudio_markers() -> None:
    for path in REFERENCE_DIR.rglob("*.ipynb"):
        assert "Repère TPStudio historique" not in path.read_text(encoding="utf-8")
        assert "Repères TPStudio historiques" not in path.read_text(encoding="utf-8")


def test_student_statements_leave_decimal_choice_to_students_with_a_guard() -> None:
    assignment = re.compile(r"(?m)^\s*(decimales\w*)\s*=\s*(.+)$")
    for path in REFERENCE_DIR.rglob("*.ipynb"):
        if "Corrige" in path.name:
            continue
        notebook = nbformat.read(path, as_version=4)
        for cell in notebook.cells:
            if cell.cell_type != "code":
                continue
            for variable, value in assignment.findall(cell.source):
                assert value.strip() == "None"
                assert f"assert {variable} is not None" in cell.source


def test_objective_prompts_invite_students_to_reread_the_statement() -> None:
    prompt = (
        "Indiquez l'objectif de cette manipulation "
        "(en relisant l'énoncé du TP si nécessaire)"
    )
    for path in REFERENCE_DIR.rglob("*.ipynb"):
        notebook = nbformat.read(path, as_version=4)
        for cell in notebook.cells:
            if "Indiquez l'objectif de cette manipulation" in cell.source:
                assert prompt in cell.source


@pytest.mark.parametrize(
    ("project_factory", "relative_path", "intentionally_absent"),
    (
        (
            snells_laws_teacher_project,
            "session-02/snells-descartes/Lois-de-Snell-Descartes-Corrige.ipynb",
            frozenset(),
        ),
        (
            thin_lens_teacher_project,
            "session-02/thin-lens/Formation-dune-image-par-une-lentille-mince-Corrige.ipynb",
            frozenset(),
        ),
        (
            focometry_teacher_project,
            "session-03/focometry/Instruments-doptique-et-application-a-la-focometrie-Corrige.ipynb",
            frozenset(),
        ),
        (
            prism_goniometer_teacher_project,
            "session-03/prism-goniometer/Mesure-dindice-au-goniometre-a-prisme-Corrige.ipynb",
            frozenset(),
        ),
    ),
)
def test_reference_correction_numeric_results_are_unambiguous(
    project_factory, relative_path: str, intentionally_absent: frozenset[str]
) -> None:
    path = REFERENCE_DIR / relative_path
    project = project_factory()
    dispatch = analyze_copy(
        NotebookCopySource(path.name, path.name, path), project=project
    )

    assert dispatch.analysis is not None
    detections = dispatch.analysis.observed_value_detections
    assert not tuple(item for item in detections if item.ambiguous)
    assert {
        item.production.id for item in detections if item.absent
    } == intentionally_absent
    assert all(
        item.unique
        for item in detections
        if item.production.id not in intentionally_absent
    )


def test_snells_reference_does_not_treat_raw_angles_as_reported_results() -> None:
    path = (
        REFERENCE_DIR
        / "session-02/snells-descartes/Lois-de-Snell-Descartes-Corrige.ipynb"
    )
    dispatch = analyze_copy(
        NotebookCopySource(path.name, path.name, path),
        project=snells_laws_teacher_project(),
    )

    assert dispatch.analysis is not None
    evaluations = dispatch.analysis.quantity_evaluations
    for production_id in (
        "critical_angle",
        "incidence_angle",
        "refraction_angle",
        "direct_index",
    ):
        assert all(
            diagnostic.code.value != "quantity_missing"
            for diagnostic in evaluations.for_production(production_id)[0].diagnostics
        )


def test_snells_reference_regression_and_plotted_fit_are_evaluable() -> None:
    path = (
        REFERENCE_DIR
        / "session-02/snells-descartes/Lois-de-Snell-Descartes-Corrige.ipynb"
    )
    dispatch = analyze_copy(
        NotebookCopySource(path.name, path.name, path),
        project=snells_laws_teacher_project(),
    )

    assert dispatch.analysis is not None
    analysis = dispatch.analysis
    measured = next(
        item for item in analysis.all_graph_analyses if item.n_points == 15
    )
    assert measured.technical_status.value == "evaluable"
    match = analysis.regression_series_matches[0]
    assert match.status.value == "exact"
    assert match.matched_series_id == measured.series_id
    model = analysis.regression_model_analyses[0]
    assert model.technical_status.value == "evaluable"
    assert model.coefficients == pytest.approx((1.4797237075, 0.0049401314))
    consistency = analysis.regression_plot_consistency_analyses[0]
    assert consistency.technical_status.value == "evaluable"
    assert consistency.consistency_status.value == "consistent"


def test_thin_lens_reference_prefers_formatted_theoretical_focal_length() -> None:
    path = (
        REFERENCE_DIR
        / "session-02/thin-lens"
        / "Formation-dune-image-par-une-lentille-mince-Corrige.ipynb"
    )
    dispatch = analyze_copy(
        NotebookCopySource(path.name, path.name, path),
        project=thin_lens_teacher_project(),
    )

    assert dispatch.analysis is not None
    evaluation = dispatch.analysis.quantity_evaluations.for_production(
        "theoretical_focal_length"
    )[0]
    observation = evaluation.assessment.selected_observation
    assert observation is not None
    assert observation.value == Decimal("30.3")
    assert observation.uncertainty == Decimal("1.0")
    assert observation.unit == "cm"
    assert not evaluation.diagnostics


def test_thin_lens_statement_supplies_theoretical_slope_without_feedback() -> None:
    path = (
        REFERENCE_DIR
        / "session-02/thin-lens"
        / "Formation-dune-image-par-une-lentille-mince-Corrige.ipynb"
    )
    dispatch = analyze_copy(
        NotebookCopySource(path.name, path.name, path),
        project=thin_lens_teacher_project(),
    )

    assert dispatch.analysis is not None
    evaluation = dispatch.analysis.quantity_evaluations.for_production(
        "theoretical_slope"
    )[0]
    observation = evaluation.assessment.selected_observation
    assert observation is not None
    assert observation.value == Decimal("1")
    assert not evaluation.diagnostics


def test_focometry_reference_recognizes_units_in_saved_text_outputs() -> None:
    path = (
        REFERENCE_DIR
        / "session-03/focometry"
        / "Instruments-doptique-et-application-a-la-focometrie-Corrige.ipynb"
    )
    dispatch = analyze_copy(
        NotebookCopySource(path.name, path.name, path),
        project=focometry_teacher_project(),
    )

    assert dispatch.analysis is not None
    for production_id in (
        "diverging_box_focal_length",
        "bessel_focal_length",
    ):
        evaluation = dispatch.analysis.quantity_evaluations.for_production(
            production_id
        )[0]
        observation = evaluation.assessment.selected_observation
        assert observation is not None
        assert observation.unit == "cm"
        assert not evaluation.diagnostics
