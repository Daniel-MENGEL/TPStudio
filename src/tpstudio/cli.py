from __future__ import annotations

import argparse
import json
from pathlib import Path

from tpstudio.parsers import LatexParser


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


def inspect_command(args: argparse.Namespace) -> int:
    tp_dir = Path(args.path).expanduser().resolve()
    tex_path = find_tex_file(tp_dir)
    document = LatexParser(tex_path).parse()

    build_dir = tp_dir / "_build"
    build_dir.mkdir(exist_ok=True)

    manifest_path = build_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(document.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_path = build_dir / "rapport_inspection.md"
    report_path.write_text(make_report(document.to_dict(), tex_path), encoding="utf-8")

    print(f"✓ Fichier LaTeX : {tex_path.name}")
    print(f"✓ Titre : {document.metadata.title or 'non détecté'}")
    print(f"✓ Objectifs : {len(document.objectives)}")
    print(f"✓ Matériel : {len(document.equipment)}")
    print(f"✓ Questions : {len(document.questions)}")
    print(f"✓ Sections détectées : {len(document.sections)}")
    print(f"✓ Manifest : {manifest_path}")
    print(f"✓ Rapport : {report_path}")
    return 0


def make_report(data: dict, tex_path: Path) -> str:
    meta = data["metadata"]
    lines = [
        "# Rapport d'inspection TPStudio",
        "",
        f"- Fichier LaTeX : `{tex_path.name}`",
        f"- Titre : {meta.get('title') or 'non détecté'}",
        f"- Séance : {meta.get('session_label') or 'non détectée'}",
        f"- Code TP : {meta.get('tp_code') or 'non détecté'}",
        f"- Slug PDF : {meta.get('pdf_slug') or 'non détecté'}",
        "",
        "## Sections détectées",
        "",
    ]
    sections = data.get("sections", [])
    if sections:
        for section in sections:
            if isinstance(section, dict):
                title = section.get("title", "Section sans titre")
                level = section.get("level", "?")
                count = len(section.get("items", []))
                lines.append(f"- {title} — niveau {level}, {count} item(s)")
            else:
                lines.append(f"- {section}")
    else:
        lines.append("Aucune section détectée.")
    lines += ["", "## Blocs pédagogiques", ""]
    for block in data.get("blocks", []):
        lines.append(f"### {block['title']} (`{block['kind']}`)")
        if block.get("items"):
            for item in block["items"]:
                lines.append(f"- {item}")
        else:
            lines.append("Aucun item détecté.")
        lines.append("")
    return "\n".join(lines)


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
