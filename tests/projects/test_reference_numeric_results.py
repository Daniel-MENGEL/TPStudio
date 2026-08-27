from pathlib import Path

import pytest

from tpstudio.orchestration import NotebookCopySource, analyze_copy
from tpstudio.projects import (
    focometry_teacher_project,
    prism_goniometer_teacher_project,
    snells_laws_teacher_project,
    thin_lens_teacher_project,
)


REFERENCE_DIR = Path(__file__).parents[2] / "reference-notebooks"


@pytest.mark.parametrize(
    ("project_factory", "relative_path", "intentionally_absent"),
    (
        (
            snells_laws_teacher_project,
            "session-02/snells-descartes/Correction-Lois-de-Snell-Descartes.ipynb",
            frozenset(),
        ),
        (
            thin_lens_teacher_project,
            "session-02/thin-lens/Correction-Formation-dune-image-par-une-lentille-mince.ipynb",
            frozenset({"theoretical_slope"}),
        ),
        (
            focometry_teacher_project,
            "session-03/focometry/Correction-Instruments-doptique-et-application-a-la-focometrie.ipynb",
            frozenset(),
        ),
        (
            prism_goniometer_teacher_project,
            "session-03/prism-goniometer/Correction-Mesure-dindice-au-goniometre-a-prisme.ipynb",
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
        / "session-02/snells-descartes/Correction-Lois-de-Snell-Descartes.ipynb"
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
        assert not evaluations.for_production(production_id)[0].diagnostics
