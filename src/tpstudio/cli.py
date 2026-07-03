from __future__ import annotations

import argparse
from pathlib import Path
from tpstudio.report_header import postprocess_improved_notebooks_in_target
from tpstudio.gradebook_export import export_gradebook_csv
from tpstudio.gradebook_check import build_gradebook_check_summary, format_gradebook_check_summary
from tpstudio.gradebook_bundle import export_gradebook_bundle
from tpstudio.gradebook_summary import write_gradebook_summary_html, write_gradebook_summary_markdown
from tpstudio.opening import choose_summary_to_open, open_path
from tpstudio.gradebook_export_guard import format_gradebook_export_blocked_message, gradebook_check_has_blocking_issues
from tpstudio.copies_summary import export_copies_summary_csv
from tpstudio.feedback_report import export_feedback_report
from tpstudio.graph_comparison import format_graph_comparison_report
from tpstudio.response_diagnostics import format_response_diagnostic_report
from tpstudio.response_extraction import format_response_extraction_report
from tpstudio.improver import improve_notebook
import json
from pathlib import Path

from tpstudio.parsers import LatexParser
from tpstudio.readers import NotebookReader
from tpstudio.reporting import format_inspection, make_inspection_report
from tpstudio.student_inspection import format_student_notebook_report, inspect_student_notebook
from tpstudio.copy_comparison import (
    compare_copy_to_model,
    format_copy_comparison_report,
    export_copy_comparison_report,
)
from tpstudio.copy_feedback import create_feedback_notebook


def find_tex_file(tp_dir: Path) -> Path:
    tex_files = sorted(p for p in tp_dir.glob("*.tex") if not p.name.startswith("."))
    if not tex_files:
        raise FileNotFoundError(f"Aucun fichier .tex trouvé dans {tp_dir}")
    if len(tex_files) == 1:
        return tex_files[0]
    # Choix simple : préférer un .tex dont le nom ressemble au dossier.
    folder_words = set(tp_dir.name.lower().replace("-", " ").split())
    scored = []
    for path in tex_files:
        words = set(path.stem.lower().replace("-", " ").split())
        scored.append((len(folder_words & words), path))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def find_notebook_file(tp_dir: Path) -> Path | None:
    """Trouve le notebook élève le plus probable dans un dossier de TP.

    Quand plusieurs notebooks sont présents, TPStudio évite les fichiers de
    correction ou de solution et préfère le notebook destiné aux étudiants.
    """

    notebook_files = sorted(
        p for p in tp_dir.glob("*.ipynb")
        if not p.name.startswith(".")
        and not p.name.endswith("-checkpoint.ipynb")
    )
    if not notebook_files:
        return None

    student_candidates = [
        path for path in notebook_files
        if not _looks_like_correction_notebook(path)
    ]

    candidates = student_candidates or notebook_files
    if len(candidates) == 1:
        return candidates[0]

    folder_words = set(tp_dir.name.lower().replace("-", " ").split())
    scored = []
    for path in candidates:
        words = set(path.stem.lower().replace("-", " ").split())
        student_bonus = 2 if _looks_like_student_notebook(path) else 0
        scored.append((len(folder_words & words) + student_bonus, path))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _looks_like_correction_notebook(path: Path) -> bool:
    name = path.stem.lower()
    correction_markers = (
        "correction",
        "ameliore",
        "amélioré",
        "amelioree",
        "améliorée",
        "corrige",
        "corrigé",
        "solution",
        "solutions",
        "prof",
        "teacher",
    )
    return any(marker in name for marker in correction_markers)


def _looks_like_student_notebook(path: Path) -> bool:
    name = path.stem.lower()
    student_markers = (
        "eleve",
        "élève",
        "etudiant",
        "étudiant",
        "student",
    )
    return any(marker in name for marker in student_markers)



def compare_copy_command(args):
    model_path = Path(args.model)
    copy_path = Path(args.copy)

    comparison = compare_copy_to_model(model_path, copy_path)
    report = format_copy_comparison_report(comparison)
    print(report)

    if getattr(args, "output", None):
        exported = export_copy_comparison_report(model_path, copy_path, Path(args.output))
        print(f"\n💾 rapport exporté : {exported}")

def feedback_copy_command(args):
    output = create_feedback_notebook(
        Path(args.model),
        Path(args.copy),
        Path(args.output) if getattr(args, "output", None) else None,
    )
    print(f"💬 notebook avec retour créé : {output}")

    return 0

def inspect_copy_command(args):
    diagnostic = inspect_student_notebook(Path(args.notebook))
    print(format_student_notebook_report(diagnostic))
    return 0

def _tpstudio_original_improve_command(args: argparse.Namespace) -> int:
    tp_dir = Path(args.path)
    output = improve_notebook(tp_dir)
    print("TPStudio - Improve")
    print("──────────────────")
    print("")
    print(f"✓ Notebook généré : {output}")
    print("")
    print("Le fichier original n'a pas été modifié.")
    return 0



def improve_command(args):
    result = _tpstudio_original_improve_command(args)

    changed = 0
    for target in _improve_targets_from_args(args):
        for postprocess_result in postprocess_improved_notebooks_in_target(target):
            if postprocess_result.changed:
                changed += 1

    if changed:
        print(f"Post-traitement improve TPStudio : {changed} notebook(s) nettoyé(s).")

    return result


def inspect_command(args: argparse.Namespace) -> int:
    tp_dir = Path(args.path).expanduser().resolve()

    try:
        tex_path = find_tex_file(tp_dir)
    except FileNotFoundError:
        print("TPStudio - Inspection")
        print("─────────────────────")
        print()
        print("❌ Aucun fichier .tex n'a été trouvé dans :")
        print()
        print(f"    {tp_dir}")
        print()
        print("Vérifiez que vous avez indiqué le dossier du TP")
        print("et non le dossier du projet TPStudio.")
        print()
        print("Exemple :")
        print('tpstudio inspect "/Users/daniel/Documents/Sup/TP/Séance n°2/Lois de Snell Descartes"')
        return 1

    document = LatexParser(tex_path).parse()
    notebook_path = find_notebook_file(tp_dir)
    notebook = NotebookReader(notebook_path).parse() if notebook_path else None
    document.notebook = notebook

    build_dir = tp_dir / "_build"
    build_dir.mkdir(exist_ok=True)

    manifest_path = build_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(document.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_path = build_dir / "rapport_inspection.md"
    report_path.write_text(
        make_inspection_report(document, tex_path, notebook),
        encoding="utf-8",
    )

    print(format_inspection(document, tex_path, manifest_path, report_path, notebook))
    return 0



def extract_responses_command(args):
    print(format_response_extraction_report(Path(args.notebook)))


def diagnose_responses_command(args):
    print(format_response_diagnostic_report(Path(args.notebook)))


def compare_graphs_command(args):
    print(format_graph_comparison_report(Path(args.model), Path(args.copy)))

def feedback_report_command(args):
    output = export_feedback_report(
        Path(args.model),
        Path(args.copy),
        Path(args.output) if args.output else None,
    )
    print(f"Rapport TPStudio créé : {output}")

def summarize_copies_command(args):
    output = export_copies_summary_csv(
        Path(args.model),
        Path(args.copies_dir),
        Path(args.output),
        pattern=args.pattern,
    )
    print(f"Synthèse TPStudio créée : {output}")

def export_gradebook_command(args) -> None:
    if getattr(args, "check_first", False):
        summary = build_gradebook_check_summary(
            Path(args.copies_dir),
            session=args.session,
            tp_name=args.tp_name,
            kholle_week=getattr(args, "week", None),
            pattern=args.pattern,
            students_file=args.students_file,
        )

        if gradebook_check_has_blocking_issues(summary) and not getattr(args, "allow_issues", False):
            print(format_gradebook_export_blocked_message(summary))
            raise SystemExit(2)

        print(format_gradebook_check_summary(summary))
        print("")

    output = export_gradebook_csv(
        Path(args.copies_dir),
        Path(args.output),
        session=args.session,
        tp_name=args.tp_name,
        week_value=getattr(args, "week", None),
        date_value=getattr(args, "date", None),
        pattern=args.pattern,
        students_file=args.students_file,
        unmatched_output_path=getattr(args, "unmatched_output", None),
        missing_output_path=getattr(args, "missing_output", None),
    )
    print(f"Fichier de suivi TPStudio créé : {output}")


def _improve_targets_from_args(args):
    targets = []
    seen = set()

    for value in vars(args).values():
        if isinstance(value, Path):
            path = value.expanduser()
        elif isinstance(value, str):
            path = Path(value).expanduser()
        else:
            continue

        try:
            resolved = path.resolve()
        except OSError:
            resolved = path

        if resolved in seen:
            continue

        if path.exists():
            seen.add(resolved)
            targets.append(path)

    return targets




def main() -> int:
    parser = argparse.ArgumentParser(prog="tpstudio")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspecte un dossier de TP")
    inspect_parser.add_argument("path", help="Chemin vers le dossier du TP")
    inspect_parser.set_defaults(func=inspect_command)

    improve_parser = subparsers.add_parser(
        "improve",
        help="crée une copie améliorée du notebook associé au TP",
    )
    improve_parser.add_argument("path", help="chemin du dossier de TP")
    improve_parser.set_defaults(func=improve_command)

    copy_parser = subparsers.add_parser(
        "inspect-copy",
        help="inspecter une copie étudiante au format notebook",
    )
    copy_parser.add_argument("notebook")
    copy_parser.set_defaults(func=inspect_copy_command)

    compare_parser = subparsers.add_parser(
        "compare-copy",
        help="comparer une copie étudiante à un notebook modèle",
    )
    compare_parser.add_argument("model")
    compare_parser.add_argument("copy")
    compare_parser.add_argument(
        "--output",
        "-o",
        help="écrit aussi le rapport dans un fichier texte",
    )
    compare_parser.set_defaults(func=compare_copy_command)

    feedback_parser = subparsers.add_parser(
        "feedback-copy",
        help="créer une copie notebook avec le retour TPStudio inséré",
    )
    feedback_parser.add_argument("model")
    feedback_parser.add_argument("copy")
    feedback_parser.add_argument(
        "--output",
        "-o",
        help="chemin du notebook à créer",
    )
    feedback_parser.set_defaults(func=feedback_copy_command)

    
    extract_responses_parser = subparsers.add_parser(
        "extract-responses",
        help="extraire les zones Réponse d'un notebook étudiant",
    )
    extract_responses_parser.add_argument("notebook")
    extract_responses_parser.set_defaults(func=extract_responses_command)
    diagnose_responses_parser = subparsers.add_parser(
        "diagnose-responses",
        help="diagnostiquer les réponses extraites d'un notebook étudiant",
    )
    diagnose_responses_parser.add_argument("notebook")
    diagnose_responses_parser.set_defaults(func=diagnose_responses_command)
    compare_graphs_parser = subparsers.add_parser(
        "compare-graphs",
        help="comparer les graphes matplotlib d'un modèle et d'une copie",
    )
    compare_graphs_parser.add_argument("model")
    compare_graphs_parser.add_argument("copy")
    compare_graphs_parser.set_defaults(func=compare_graphs_command)




    feedback_report_parser = subparsers.add_parser(
        "feedback-report",
        help="exporter un rapport Markdown TPStudio pour une copie",
    )
    feedback_report_parser.add_argument("model")
    feedback_report_parser.add_argument("copy")
    feedback_report_parser.add_argument("--output", "-o")
    feedback_report_parser.set_defaults(func=feedback_report_command)


    summarize_copies_parser = subparsers.add_parser(
        "summarize-copies",
        help="résumer plusieurs copies dans un fichier CSV",
    )
    summarize_copies_parser.add_argument("model")
    summarize_copies_parser.add_argument("copies_dir")
    summarize_copies_parser.add_argument("--output", "-o", required=True)
    summarize_copies_parser.add_argument("--pattern", default="*.ipynb")
    summarize_copies_parser.set_defaults(func=summarize_copies_command)


    export_gradebook_parser = subparsers.add_parser(
        "export-gradebook",
        help="exporter un CSV de suivi pédagogique pour une séance de TP",
    )
    export_gradebook_parser.add_argument("copies_dir")
    export_gradebook_parser.add_argument("--session", required=True)
    export_gradebook_parser.add_argument("--tp-name", required=True)
    export_gradebook_parser.add_argument("--date")
    export_gradebook_parser.add_argument("--week", "--kholle-week", dest="week")
    export_gradebook_parser.add_argument("--students-file")
    export_gradebook_parser.add_argument("--unmatched-output")
    export_gradebook_parser.add_argument("--missing-output")
    export_gradebook_parser.add_argument("--output", "-o", required=True)
    export_gradebook_parser.add_argument("--pattern", default="*.ipynb")
    export_gradebook_parser.add_argument("--check-first", action="store_true")
    export_gradebook_parser.add_argument("--allow-issues", action="store_true")
    export_gradebook_parser.set_defaults(func=export_gradebook_command)

    export_gradebook_bundle_parser = subparsers.add_parser(
        "export-gradebook-bundle",
        help="exporter le suivi complet avec noms de fichiers automatiques",
        description="Génère les CSV de suivi, anomalies et rapports non rendus pour une séance de TP.",
    )
    export_gradebook_bundle_parser.add_argument("copies_dir")
    export_gradebook_bundle_parser.add_argument("--session", required=True)
    export_gradebook_bundle_parser.add_argument("--tp-name", required=True)
    export_gradebook_bundle_parser.add_argument("--week", "--kholle-week", dest="week")
    export_gradebook_bundle_parser.add_argument("--date")
    export_gradebook_bundle_parser.add_argument("--pattern", default="*.ipynb")
    export_gradebook_bundle_parser.add_argument("--students-file")
    export_gradebook_bundle_parser.add_argument("--output-dir")
    export_gradebook_bundle_parser.add_argument("--prefix")
    export_gradebook_bundle_parser.add_argument("--check-first", action="store_true")
    export_gradebook_bundle_parser.add_argument("--allow-issues", action="store_true")
    export_gradebook_bundle_parser.add_argument("--summary-md", action="store_true")
    export_gradebook_bundle_parser.add_argument("--summary-html", action="store_true")
    export_gradebook_bundle_parser.add_argument("--open-summary", action="store_true")
    export_gradebook_bundle_parser.add_argument("--open-folder", action="store_true")
    export_gradebook_bundle_parser.set_defaults(func=export_gradebook_bundle_command)


    check_gradebook_parser = subparsers.add_parser(
        "check-gradebook",
        help="contrôler rapidement un dossier de copies sans exporter",
        description="Affiche un résumé des copies, anomalies, identités absentes et rapports non rendus.",
    )
    check_gradebook_parser.add_argument("copies_dir")
    check_gradebook_parser.add_argument("--session", required=True)
    check_gradebook_parser.add_argument("--tp-name", required=True)
    check_gradebook_parser.add_argument("--week", "--kholle-week", dest="week")
    check_gradebook_parser.add_argument("--pattern", default="*.ipynb")
    check_gradebook_parser.add_argument("--students-file")
    check_gradebook_parser.set_defaults(func=check_gradebook_command)


    args = parser.parse_args()
    return args.func(args)


def check_gradebook_command(args) -> None:
    summary = build_gradebook_check_summary(
        Path(args.copies_dir),
        session=args.session,
        tp_name=args.tp_name,
        kholle_week=args.week,
        pattern=args.pattern,
        students_file=args.students_file,
    )
    print(format_gradebook_check_summary(summary))

def export_gradebook_bundle_command(args) -> None:
    summary = None

    if (
        getattr(args, "check_first", False)
        or getattr(args, "summary_md", False)
        or getattr(args, "summary_html", False)
    ):
        summary = build_gradebook_check_summary(
            Path(args.copies_dir),
            session=args.session,
            tp_name=args.tp_name,
            kholle_week=getattr(args, "week", None),
            pattern=args.pattern,
            students_file=args.students_file,
        )

    if getattr(args, "check_first", False):
        if gradebook_check_has_blocking_issues(summary) and not getattr(args, "allow_issues", False):
            print(format_gradebook_export_blocked_message(summary))
            raise SystemExit(2)

        print(format_gradebook_check_summary(summary))
        print("")

    paths = export_gradebook_bundle(
        Path(args.copies_dir),
        session=args.session,
        tp_name=args.tp_name,
        kholle_week=getattr(args, "week", None),
        date_value=getattr(args, "date", None),
        pattern=args.pattern,
        students_file=args.students_file,
        output_dir=args.output_dir,
        prefix=args.prefix,
    )

    print("Bundle de suivi TPStudio créé :")
    print(f"- Suivi : {paths.followup_csv}")
    print(f"- Anomalies : {paths.unmatched_csv}")
    print(f"- Rapports non rendus : {paths.missing_csv}")

    markdown_summary_path = None
    html_summary_path = None

    if getattr(args, "summary_md", False):
        markdown_summary_path = paths.followup_csv.with_name(
            paths.followup_csv.name.removesuffix("-suivi.csv") + "-bilan.md"
        )
        written = write_gradebook_summary_markdown(
            markdown_summary_path,
            copies_dir=Path(args.copies_dir),
            session=args.session,
            tp_name=args.tp_name,
            kholle_week=getattr(args, "week", None),
            pattern=args.pattern,
            students_file=args.students_file,
            bundle_paths=paths,
            check_summary=summary,
        )
        markdown_summary_path = written.path
        print(f"- Bilan Markdown : {written.path}")

    if getattr(args, "summary_html", False):
        html_summary_path = paths.followup_csv.with_name(
            paths.followup_csv.name.removesuffix("-suivi.csv") + "-bilan.html"
        )
        written = write_gradebook_summary_html(
            html_summary_path,
            copies_dir=Path(args.copies_dir),
            session=args.session,
            tp_name=args.tp_name,
            kholle_week=getattr(args, "week", None),
            pattern=args.pattern,
            students_file=args.students_file,
            bundle_paths=paths,
            check_summary=summary,
        )
        html_summary_path = written.path
        print(f"- Bilan HTML : {written.path}")

    if getattr(args, "open_summary", False):
        summary_to_open = choose_summary_to_open(
            html_path=html_summary_path,
            markdown_path=markdown_summary_path,
        )

        if summary_to_open is None:
            print("Aucun bilan à ouvrir. Ajoute --summary-html ou --summary-md.")
        else:
            open_path(summary_to_open)
            print(f"Ouverture du bilan : {summary_to_open}")

    if getattr(args, "open_folder", False):
        folder_to_open = paths.followup_csv.parent
        open_path(folder_to_open)
        print(f"Ouverture du dossier : {folder_to_open}")

if __name__ == "__main__":
    main()
