from __future__ import annotations

import argparse
import json
from pathlib import Path

from tpstudio.parsers import LatexParser
from tpstudio.readers import NotebookReader
from tpstudio.reporting import format_inspection, make_inspection_report


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
    notebook_files = sorted(p for p in tp_dir.glob("*.ipynb") if not p.name.startswith("."))
    if not notebook_files:
        return None
    if len(notebook_files) == 1:
        return notebook_files[0]

    folder_words = set(tp_dir.name.lower().replace("-", " ").split())
    scored = []
    for path in notebook_files:
        words = set(path.stem.lower().replace("-", " ").split())
        scored.append((len(folder_words & words), path))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


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


def main() -> int:
    parser = argparse.ArgumentParser(prog="tpstudio")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspecte un dossier de TP")
    inspect_parser.add_argument("path", help="Chemin vers le dossier du TP")
    inspect_parser.set_defaults(func=inspect_command)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
