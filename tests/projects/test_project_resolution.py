import nbformat

from tpstudio.projects import (
    ProjectResolutionConfidence,
    ProjectEvidenceCategory,
    known_project_ids,
    resolve_project_for_copy,
)


def notebook(*markdown: str, code: tuple[str, ...] = ()):
    return nbformat.v4.new_notebook(cells=[
        *(nbformat.v4.new_markdown_cell(item) for item in markdown),
        *(nbformat.v4.new_code_cell(item) for item in code),
    ])


def test_registry_contains_projects_in_stable_order() -> None:
    assert known_project_ids() == (
        "snells-laws-mvp",
        "thin-lens-image",
        "optical-instruments-focometry",
        "torsion-pendulum",
        "first-order-transient",
        "first-lab-measurements",
    )


def test_snell_clear_resolves_high() -> None:
    result = resolve_project_for_copy(notebook(
        "# Lois de Snell-Descartes",
        "Étudier la réfraction et l'indice de réfraction.",
        "Tracer sin(i1) en fonction de sin(i2).",
    ))
    assert result.selected_project_id == "snells-laws-mvp"
    assert result.requires_teacher_choice is False
    assert result.candidates[0].confidence is ProjectResolutionConfidence.HIGH


def test_thin_lens_clear_resolves_high() -> None:
    result = resolve_project_for_copy(notebook(
        "# Formation d'une image par une lentille mince",
        "Relation de conjugaison : 1/OA' - 1/OA = 1/f'.",
    ))
    assert result.selected_project_id == "thin-lens-image"
    assert result.candidates[0].confidence is ProjectResolutionConfidence.HIGH


def test_focometry_clear_resolves_high() -> None:
    result = resolve_project_for_copy(notebook(
        "# Instruments d'optique et application à la focométrie",
        "Méthodes d'autocollimation, de Bessel et utilisation d'un collimateur.",
    ))
    assert result.selected_project_id == "optical-instruments-focometry"
    assert result.requires_teacher_choice is False


def test_first_lab_measurements_clear_resolves_high() -> None:
    result = resolve_project_for_copy(notebook(
        "# Premières mesures au labo",
        "Déterminer les raideurs dynamique et statique du ressort.",
        code=("k_dyn_samples = ...\nk_static_samples = ...",),
    ))
    assert result.selected_project_id == "first-lab-measurements"
    assert result.requires_teacher_choice is False
    assert result.candidates[0].confidence is ProjectResolutionConfidence.HIGH


def test_strong_signatures_work_without_title() -> None:
    snell = resolve_project_for_copy(notebook(
        "Étudier la réfraction et l'indice de réfraction.",
        "Tracer sin(i1) en fonction de sin(i2).",
    ))
    lens = resolve_project_for_copy(notebook(
        "Relation de conjugaison : 1/OA' - 1/OA = 1/f'.",
        "Déterminer la distance focale.",
    ))
    assert snell.selected_project_id == "snells-laws-mvp"
    assert lens.selected_project_id == "thin-lens-image"


def test_generic_notebook_abstains() -> None:
    result = resolve_project_for_copy(notebook("Effectuer les mesures.", "Tracer le graphe.", "Faire une régression."))
    assert result.selected_project_id is None
    assert result.candidates == ()
    assert result.requires_teacher_choice is False


def test_empty_notebook_abstains_without_snell_fallback() -> None:
    result = resolve_project_for_copy(notebook())
    assert result.selected_project_id is None
    assert result.candidates == ()


def test_filename_alone_is_weak_and_never_selects() -> None:
    result = resolve_project_for_copy(notebook(), filename="TP_Snell.ipynb")
    assert result.selected_project_id is None
    assert result.requires_teacher_choice is True
    assert result.candidates[0].confidence is ProjectResolutionConfidence.LOW


def test_high_snell_beats_weak_lens_filename_noise() -> None:
    result = resolve_project_for_copy(
        notebook("# Lois de Snell-Descartes", "Étudier la réfraction et l'indice."),
        filename="copie_lentille.ipynb",
    )
    assert result.selected_project_id == "snells-laws-mvp"


def test_high_snell_beats_medium_lens_candidate() -> None:
    result = resolve_project_for_copy(notebook(
        "# Lois de Snell-Descartes",
        "Étudier la réfraction et l'indice.",
        "Les grandeurs OA et d0 sont mentionnées.",
        "Tracer sin(i1) en fonction de sin(i2).",
    ))
    assert result.selected_project_id == "snells-laws-mvp"
    assert result.requires_teacher_choice is False
    assert [item.project_id for item in result.candidates] == [
        "snells-laws-mvp", "thin-lens-image",
    ]
    assert result.candidates[1].confidence is ProjectResolutionConfidence.MEDIUM


def test_high_high_conflict_requires_teacher_choice() -> None:
    result = resolve_project_for_copy(notebook(
        "# Lois de Snell-Descartes",
        "Étudier la réfraction et l'indice.",
        "# Formation d'une image par une lentille mince",
        "Relation de conjugaison : 1/OA' - 1/OA = 1/f'.",
    ))
    assert result.selected_project_id is None
    assert result.requires_teacher_choice is True
    assert {item.project_id for item in result.candidates} == {"snells-laws-mvp", "thin-lens-image"}


def test_medium_medium_conflict_requires_teacher_choice() -> None:
    result = resolve_project_for_copy(notebook(
        "Tracer sin(i1) en fonction de sin(i2).",
        "Les grandeurs OA et d0 sont relevées.",
    ))
    assert result.selected_project_id is None
    assert result.requires_teacher_choice is True
    assert {item.confidence for item in result.candidates} == {ProjectResolutionConfidence.MEDIUM}


def test_explicit_filename_alone_is_not_automatic() -> None:
    result = resolve_project_for_copy(
        notebook(), filename="Formation-dune-image-par-une-lentille-mince.ipynb"
    )
    assert result.selected_project_id is None
    assert result.requires_teacher_choice is True
    assert result.candidates[0].confidence is ProjectResolutionConfidence.LOW


def test_explicit_project_bypasses_detection() -> None:
    result = resolve_project_for_copy(notebook(), explicit_project_id="thin-lens-image")
    assert result.selected_project_id == "thin-lens-image"
    assert result.requires_teacher_choice is False
    assert result.candidates[0].evidence[0].category is ProjectEvidenceCategory.STRONG


def test_unknown_explicit_project_is_rejected() -> None:
    try:
        resolve_project_for_copy(notebook(), explicit_project_id="unknown")
    except ValueError:
        pass
    else:
        raise AssertionError("Un projet explicite inconnu doit être rejeté.")


def test_code_signatures_are_not_high_alone() -> None:
    result = resolve_project_for_copy(notebook(code=("import numpy as np\nnp.sin(i1)",)))
    assert result.selected_project_id is None
    assert all(item.confidence is not ProjectResolutionConfidence.HIGH for item in result.candidates)


def test_evidence_order_is_deterministic() -> None:
    value = notebook("# Lois de Snell-Descartes", "Étudier la réfraction et l'indice.")
    first = resolve_project_for_copy(value)
    second = resolve_project_for_copy(value)
    assert first == second


def test_structured_project_metadata_is_not_required() -> None:
    result = resolve_project_for_copy(notebook(
        "# Formation d'une image par une lentille mince",
        "Relation de conjugaison : 1/OA' - 1/OA = 1/f'.",
    ))
    assert result.selected_project_id == "thin-lens-image"
