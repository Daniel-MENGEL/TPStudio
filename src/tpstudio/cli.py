from __future__ import annotations

import argparse
from pathlib import Path
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

def improve_command(args: argparse.Namespace) -> int:
    tp_dir = Path(args.path)
    output = improve_notebook(tp_dir)
    print("TPStudio - Improve")
    print("──────────────────")
    print("")
    print(f"✓ Notebook généré : {output}")
    print("")
    print("Le fichier original n'a pas été modifié.")
    return 0


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


    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
