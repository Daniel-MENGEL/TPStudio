from pathlib import Path

import nbformat
import pytest

from tpstudio.web.identity import (
    CopyIdentity, CopyIdentitySource, CopyIdentityStatus, StudentIdentity,
    build_canonical_copy_stem, canonical_tp_name, extract_copy_identity_from_notebook,
    extract_identity_hint_from_filename, resolve_copy_identity,
)
from tpstudio.web.model import SelectedCopy
from tpstudio.web.planning import identify_selected_copy


def _notebook(text: str):
    return nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell(text)])


@pytest.mark.parametrize("label", ["Noms", "Nom(s)", "Étudiants", "Etudiants", "Binôme"])
@pytest.mark.parametrize("separator", [" et ", ", ", " ; ", " / "])
def test_notebook_identity_patterns(tmp_path, label, separator):
    path = tmp_path / "copy.ipynb"
    nbformat.write(_notebook(f"**{label} :** Jules BERNARD{separator}Daniel MENGEL"), path)
    identity = extract_copy_identity_from_notebook(path)
    assert identity.status is CopyIdentityStatus.CONFIRMED
    assert [student.display_name for student in identity.students] == ["Jules BERNARD", "Daniel MENGEL"]
    assert identity.source is CopyIdentitySource.NOTEBOOK


def test_markdown_context_and_placeholders(tmp_path):
    path = tmp_path / "copy.ipynb"
    nbformat.write(_notebook("# Identification du compte rendu\n\n**Noms :** à compléter\n\n**Groupe :** 4"), path)
    identity = extract_copy_identity_from_notebook(path)
    assert identity.status is CopyIdentityStatus.MISSING and not identity.students


def test_filename_is_only_a_review_hint():
    assert extract_identity_hint_from_filename("Untitled.ipynb") == ()
    hint = extract_identity_hint_from_filename("TP-Snell-Jules-Bernard-Daniel-Mengel.ipynb")
    assert hint and resolve_copy_identity(CopyIdentity((), None, CopyIdentityStatus.MISSING), filename_hint=hint).status is CopyIdentityStatus.TO_REVIEW


def test_notebook_filename_compatibility_and_divergence(tmp_path):
    path = tmp_path / "Jules-Bernard-Daniel-Mengel.ipynb"
    nbformat.write(_notebook("Noms : Jules BERNARD et Daniel MENGEL"), path)
    selected = SelectedCopy("copy-001", path.name, path, "0" * 64)
    # identity extraction itself is notebook-only; resolution supplies filename evidence.
    identity = extract_copy_identity_from_notebook(path)
    assert resolve_copy_identity(identity, filename_hint=extract_identity_hint_from_filename(path.name)).status is CopyIdentityStatus.CONFIRMED
    divergent = resolve_copy_identity(identity, filename_hint=("Paul", "DURAND"))
    assert divergent.status is CopyIdentityStatus.TO_REVIEW and divergent.warnings


@pytest.mark.parametrize("filename", [
    "Lois-de-Snell-Descartes-Daniel et Jules.ipynb",
    "Jules-BERNARD-Daniel-MENGEL.ipynb",
    "Daniel-et-Jules.ipynb",
    "Bernard-Mengel.ipynb",
    "Jules-Mengel.ipynb",
    "TP-Snell-2025-09-22.ipynb",
    "Untitled.ipynb",
])
def test_partial_or_neutral_filename_does_not_degrade_notebook_identity(filename):
    identity = CopyIdentity((StudentIdentity("Jules BERNARD"), StudentIdentity("Daniel MENGEL")), CopyIdentitySource.NOTEBOOK, CopyIdentityStatus.CONFIRMED)
    resolved = resolve_copy_identity(identity, filename_hint=extract_identity_hint_from_filename(filename))
    assert resolved.status is CopyIdentityStatus.CONFIRMED
    assert resolved.source is CopyIdentitySource.NOTEBOOK


def test_strongly_contradictory_filename_requires_review():
    identity = CopyIdentity((StudentIdentity("Jules BERNARD"), StudentIdentity("Daniel MENGEL")), CopyIdentitySource.NOTEBOOK, CopyIdentityStatus.CONFIRMED)
    resolved = resolve_copy_identity(identity, filename_hint=extract_identity_hint_from_filename("Paul-DURAND-Marie-MARTIN.ipynb"))
    assert resolved.status is CopyIdentityStatus.TO_REVIEW
    assert resolved.warnings == ("Le nom du fichier semble indiquer une identité différente.",)


def test_canonical_stem_preserves_declared_order_and_sanitizes():
    identity = CopyIdentity((StudentIdentity("Jules BERNARD"), StudentIdentity("Léa D'Ange / Martin")), None, CopyIdentityStatus.CONFIRMED)
    assert build_canonical_copy_stem(canonical_tp_name("snells-laws-mvp"), identity) == "Lois-de-Snell-Descartes-Jules-BERNARD-Léa-D-Ange-Martin"
    assert build_canonical_copy_stem("TP", replace_identity(identity, CopyIdentityStatus.TO_REVIEW)) is None


def replace_identity(identity, status):
    return CopyIdentity(identity.students, identity.source, status, identity.raw_value, identity.warnings)


def test_identify_selected_copy_enriches_without_writing(tmp_path):
    path = tmp_path / "copy.ipynb"; nbformat.write(_notebook("Noms : Jules BERNARD et Daniel MENGEL"), path)
    selected = SelectedCopy("copy-001", path.name, path, "0" * 64)
    enriched = identify_selected_copy(selected)
    assert enriched.identity is not None and enriched.identity.status is CopyIdentityStatus.CONFIRMED
