from dataclasses import replace
from pathlib import Path
import importlib.util

from tpstudio.reporting import build_teacher_copy_report, render_teacher_report_markdown, summarize_teacher_report


def _result(tmp_path):
    path = Path("tests/orchestration/test_copy_analysis.py")
    spec = importlib.util.spec_from_file_location("copy_markdown_fixture", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module._analyze(tmp_path)


def test_markdown_contains_all_canonical_sections(tmp_path) -> None:
    report = build_teacher_copy_report(_result(tmp_path))
    text = render_teacher_report_markdown(report)
    for title in ("Retour TPStudio", "Synthèse rapide", "Priorités de revue", "État technique et exécution enregistrée", "Productions attendues", "Valeurs observées", "Résultats quantitatifs", "Relations scientifiques", "Graphe et régression", "Comparaisons quantitatives", "Conclusion finale", "Diagnostics", "Retours configurés", "Conseils ciblés", "Limites de l’analyse", "Revue humaine"):
        assert title in text
    assert "En objectif" in text and "En étudiant" in text
    assert "Interprétation A70e" in text and "Justification A70g" in text


def test_markdown_is_deterministic_private_plain_markdown(tmp_path) -> None:
    report = build_teacher_copy_report(_result(tmp_path))
    first = render_teacher_report_markdown(report)
    assert first == render_teacher_report_markdown(report)
    assert str(tmp_path) not in first
    assert "<html" not in first.lower() and "<script" not in first.lower()
    assert "score" not in first.lower() and "note automatique" in first.lower()


def test_console_summary_is_compact_and_private(tmp_path) -> None:
    text = summarize_teacher_report(build_teacher_copy_report(_result(tmp_path)))
    assert "Project: snells-laws-mvp" in text and "Human review:" in text
    assert str(tmp_path) not in text


def test_markdown_shows_counts_but_never_external_path_strings(tmp_path) -> None:
    result = _result(tmp_path)
    private = "/Users/example/private/data.csv"
    inspection = replace(
        result.technical_inspection,
        referenced_external_paths=(private,),
    )
    report = build_teacher_copy_report(replace(result, technical_inspection=inspection))
    text = render_teacher_report_markdown(report)
    assert "Références à des chemins externes détectées : 1" in text
    assert private not in text and private not in repr(report)
    assert "Quantités :" in text and "non évaluables" in text
    assert "Limitations déclarées" in text
