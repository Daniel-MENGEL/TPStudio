from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path


@dataclass
class StudentNotebookDiagnostic:
    path: Path
    total_cells: int
    markdown_cells: int
    code_cells: int
    response_cells: int
    empty_response_cells: int
    filled_response_cells: int
    code_cells_with_outputs: int
    code_cells_without_outputs: int
    code_cells_not_executed: int
    code_cells_with_errors: int
    headings: int

    @property
    def has_response_zones(self) -> bool:
        return self.response_cells > 0

    @property
    def has_code_issues(self) -> bool:
        return self.code_cells_not_executed > 0 or self.code_cells_with_errors > 0


def inspect_student_notebook(notebook_path: str | Path) -> StudentNotebookDiagnostic:
    path = Path(notebook_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    cells = data.get("cells", [])
    if not isinstance(cells, list):
        cells = []

    total_cells = len(cells)
    markdown_cells = 0
    code_cells = 0
    response_cells = 0
    empty_response_cells = 0
    code_cells_with_outputs = 0
    code_cells_without_outputs = 0
    code_cells_not_executed = 0
    code_cells_with_errors = 0
    headings = 0

    for cell in cells:
        cell_type = cell.get("cell_type")
        text = _cell_text(cell)

        if cell_type == "markdown":
            markdown_cells += 1
            headings += _count_markdown_headings(text)

            if _contains_response_marker(text):
                response_cells += 1
                if _is_empty_response(text):
                    empty_response_cells += 1

        elif cell_type == "code":
            code_cells += 1

            outputs = cell.get("outputs", [])
            if outputs:
                code_cells_with_outputs += 1
            else:
                code_cells_without_outputs += 1

            if cell.get("execution_count") is None:
                code_cells_not_executed += 1

            if _has_error_output(outputs):
                code_cells_with_errors += 1

    filled_response_cells = response_cells - empty_response_cells

    return StudentNotebookDiagnostic(
        path=path,
        total_cells=total_cells,
        markdown_cells=markdown_cells,
        code_cells=code_cells,
        response_cells=response_cells,
        empty_response_cells=empty_response_cells,
        filled_response_cells=filled_response_cells,
        code_cells_with_outputs=code_cells_with_outputs,
        code_cells_without_outputs=code_cells_without_outputs,
        code_cells_not_executed=code_cells_not_executed,
        code_cells_with_errors=code_cells_with_errors,
        headings=headings,
    )


def format_student_notebook_report(diagnostic: StudentNotebookDiagnostic) -> str:
    lines: list[str] = []

    lines.append("TPStudio - Inspection de copie")
    lines.append("─────────────────────────────")
    lines.append("")
    lines.append(f"📓 Notebook : {diagnostic.path.name}")
    lines.append(f"    • cellules : {diagnostic.total_cells}")
    lines.append(f"    • markdown : {diagnostic.markdown_cells}")
    lines.append(f"    • code : {diagnostic.code_cells}")
    lines.append(f"    • titres Markdown : {diagnostic.headings}")
    lines.append("")

    lines.append("📝 Réponses")
    if diagnostic.response_cells == 0:
        lines.append("    ⚠ aucune cellule contenant « Réponse : »")
    else:
        lines.append(f"    • cellules avec Réponse : {diagnostic.response_cells}")
        lines.append(f"    • réponses complétées : {diagnostic.filled_response_cells}")
        lines.append(f"    • réponses vides ou à compléter : {diagnostic.empty_response_cells}")
    lines.append("")

    lines.append("💻 Code")
    if diagnostic.code_cells == 0:
        lines.append("    ℹ aucune cellule de code")
    else:
        lines.append(f"    • cellules avec sortie : {diagnostic.code_cells_with_outputs}")
        lines.append(f"    • cellules sans sortie : {diagnostic.code_cells_without_outputs}")
        lines.append(f"    • cellules non exécutées : {diagnostic.code_cells_not_executed}")
        lines.append(f"    • cellules avec erreur : {diagnostic.code_cells_with_errors}")
    lines.append("")

    lines.append("🧭 Diagnostic provisoire")
    if not diagnostic.has_response_zones:
        lines.append("    ⚠ copie difficile à corriger automatiquement : aucune zone « Réponse : » détectée")
    elif diagnostic.empty_response_cells:
        lines.append("    ⚠ certaines réponses semblent vides ou non complétées")
    else:
        lines.append("    ✓ zones de réponse présentes et apparemment complétées")

    if diagnostic.code_cells_with_errors:
        lines.append("    ⚠ des erreurs d'exécution sont présentes")
    elif diagnostic.code_cells_not_executed:
        lines.append("    ⚠ certaines cellules de code n'ont pas été exécutées")
    elif diagnostic.code_cells:
        lines.append("    ✓ les cellules de code semblent exécutées")

    return "\n".join(lines)


def _cell_text(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source)


def _count_markdown_headings(text: str) -> int:
    return sum(1 for line in text.splitlines() if re.match(r"^#{1,6}\s+", line.strip()))


def _contains_response_marker(text: str) -> bool:
    return re.search(r"réponse\s*:", text, flags=re.I) is not None


def _is_empty_response(text: str) -> bool:
    match = re.search(r"réponse\s*:", text, flags=re.I)
    if not match:
        return False

    answer = text[match.end():]
    answer = re.sub(r"[*_`#>\-\s]+", " ", answer)
    answer = answer.strip(" .:\n\t").lower()

    if not answer:
        return True

    placeholders = {
        "a completer",
        "à compléter",
        "todo",
        "reponse",
        "réponse",
        "...",
    }

    normalized = answer.replace("é", "e").replace("è", "e").replace("ê", "e")
    return answer in placeholders or normalized in placeholders


def _has_error_output(outputs: object) -> bool:
    if not isinstance(outputs, list):
        return False

    for output in outputs:
        if isinstance(output, dict) and output.get("output_type") == "error":
            return True

    return False
