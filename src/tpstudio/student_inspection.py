from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from pathlib import Path


@dataclass
class StudentCellIssue:
    cell_number: int
    severity: str
    kind: str
    message: str
    preview: str = ""


@dataclass
class StudentGlobalIssue:
    severity: str
    kind: str
    message: str


@dataclass
class CorrectionReadiness:
    level: str
    score: int
    max_score: int
    reasons: list[str] = field(default_factory=list)


@dataclass
class StudentNotebookDiagnostic:
    path: Path
    total_cells: int
    markdown_cells: int
    code_cells: int
    empty_code_cells: int
    response_cells: int
    empty_response_cells: int
    filled_response_cells: int
    result_cells: int
    interpretation_cells: int
    checklist_cells: int
    code_cells_with_outputs: int
    code_cells_without_outputs: int
    code_cells_not_executed: int
    code_cells_with_errors: int
    headings: int
    issues: list[StudentCellIssue] = field(default_factory=list)
    global_issues: list[StudentGlobalIssue] = field(default_factory=list)
    correction_readiness: CorrectionReadiness | None = None

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
    empty_code_cells = 0
    response_cells = 0
    empty_response_cells = 0
    result_cells = 0
    interpretation_cells = 0
    checklist_cells = 0
    code_cells_with_outputs = 0
    code_cells_without_outputs = 0
    code_cells_not_executed = 0
    code_cells_with_errors = 0
    headings = 0
    issues: list[StudentCellIssue] = []

    for index, cell in enumerate(cells):
        cell_number = index + 1
        cell_type = cell.get("cell_type")
        text = _cell_text(cell)

        if cell_type == "markdown":
            markdown_cells += 1
            headings += _count_markdown_headings(text)

            if _contains_result_marker(text):
                result_cells += 1

            if _contains_interpretation_marker(text):
                interpretation_cells += 1

            if _contains_checklist_marker(text):
                checklist_cells += 1

            if _contains_response_marker(text):
                response_cells += 1

                if _is_empty_response(text):
                    empty_response_cells += 1
                    issues.append(
                        StudentCellIssue(
                            cell_number=cell_number,
                            severity="warning",
                            kind="empty_response",
                            message="réponse vide ou à compléter",
                            preview=_preview(text),
                        )
                    )
                elif _is_short_response(text):
                    issues.append(
                        StudentCellIssue(
                            cell_number=cell_number,
                            severity="info",
                            kind="short_response",
                            message="réponse très courte à relire",
                            preview=_preview(text),
                        )
                    )

        elif cell_type == "code":
            code_cells += 1

            if _is_effectively_empty_code(text):
                empty_code_cells += 1
                continue

            outputs = cell.get("outputs", [])
            has_outputs = bool(outputs)

            if has_outputs:
                code_cells_with_outputs += 1
            else:
                code_cells_without_outputs += 1

            if cell.get("execution_count") is None:
                code_cells_not_executed += 1
                issues.append(
                    StudentCellIssue(
                        cell_number=cell_number,
                        severity="warning",
                        kind="not_executed",
                        message="cellule de code non exécutée",
                        preview=_preview(text),
                    )
                )
            elif not has_outputs and _code_likely_expected_output(text):
                issues.append(
                    StudentCellIssue(
                        cell_number=cell_number,
                        severity="info",
                        kind="missing_output",
                        message="cellule de code exécutée sans sortie visible",
                        preview=_preview(text),
                    )
                )

            if _has_error_output(outputs):
                code_cells_with_errors += 1
                issues.append(
                    StudentCellIssue(
                        cell_number=cell_number,
                        severity="warning",
                        kind="execution_error",
                        message="erreur d'exécution présente",
                        preview=_preview(text),
                    )
                )

    filled_response_cells = response_cells - empty_response_cells
    executable_code_cells = code_cells - empty_code_cells

    global_issues = _global_issues_for_copy(
        markdown_cells=markdown_cells,
        code_cells=code_cells,
        executable_code_cells=executable_code_cells,
        response_cells=response_cells,
        code_cells_not_executed=code_cells_not_executed,
        code_cells_with_errors=code_cells_with_errors,
    )

    correction_readiness = _correction_readiness_for_copy(
        response_cells=response_cells,
        empty_response_cells=empty_response_cells,
        result_cells=result_cells,
        interpretation_cells=interpretation_cells,
        checklist_cells=checklist_cells,
        headings=headings,
        executable_code_cells=executable_code_cells,
        code_cells_not_executed=code_cells_not_executed,
        code_cells_with_errors=code_cells_with_errors,
    )

    return StudentNotebookDiagnostic(
        path=path,
        total_cells=total_cells,
        markdown_cells=markdown_cells,
        code_cells=code_cells,
        empty_code_cells=empty_code_cells,
        response_cells=response_cells,
        empty_response_cells=empty_response_cells,
        filled_response_cells=filled_response_cells,
        result_cells=result_cells,
        interpretation_cells=interpretation_cells,
        checklist_cells=checklist_cells,
        code_cells_with_outputs=code_cells_with_outputs,
        code_cells_without_outputs=code_cells_without_outputs,
        code_cells_not_executed=code_cells_not_executed,
        code_cells_with_errors=code_cells_with_errors,
        headings=headings,
        issues=issues,
        global_issues=global_issues,
        correction_readiness=correction_readiness,
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
    if diagnostic.empty_code_cells:
        lines.append(f"    • code vide ignoré : {diagnostic.empty_code_cells}")
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

    lines.append("🧩 Structure attendue")
    lines.append(f"    • cellules Résultat : {diagnostic.result_cells}")
    lines.append(f"    • cellules d'interprétation : {diagnostic.interpretation_cells}")
    lines.append(f"    • checklist / grille : {diagnostic.checklist_cells}")
    lines.append("")

    lines.append("💻 Code")
    if diagnostic.code_cells == 0:
        lines.append("    ℹ aucune cellule de code")
    else:
        if diagnostic.empty_code_cells:
            lines.append(f"    • cellules de code vides ignorées : {diagnostic.empty_code_cells}")
        lines.append(f"    • cellules avec sortie : {diagnostic.code_cells_with_outputs}")
        lines.append(f"    • cellules sans sortie : {diagnostic.code_cells_without_outputs}")
        lines.append(f"    • cellules non exécutées : {diagnostic.code_cells_not_executed}")
        lines.append(f"    • cellules avec erreur : {diagnostic.code_cells_with_errors}")
    lines.append("")

    lines.append("🔎 Cellules à vérifier")
    if not diagnostic.issues:
        lines.append("    ✓ aucune cellule problématique évidente détectée")
    else:
        for issue in diagnostic.issues:
            symbol = _severity_symbol(issue.severity)
            line = f"    {symbol} cellule {issue.cell_number} — {issue.message}"
            if issue.preview:
                line += f" : {issue.preview}"
            lines.append(line)
    lines.append("")

    lines.append("⚠ Points globaux à vérifier")
    if not diagnostic.global_issues:
        lines.append("    ✓ aucun point global évident détecté")
    else:
        for issue in diagnostic.global_issues:
            symbol = _severity_symbol(issue.severity)
            lines.append(f"    {symbol} {issue.message}")
    lines.append("")

    lines.append("🧪 Corrigeabilité automatique")
    readiness = diagnostic.correction_readiness
    if readiness is None:
        lines.append("    ℹ non évaluée")
    else:
        lines.append(f"    niveau : {readiness.level} ({readiness.score}/{readiness.max_score})")
        for reason in readiness.reasons:
            lines.append(f"    • {reason}")
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
        lines.append("    ✓ les cellules de code semblent exécutées ou vides")

    return "\n".join(lines)


def _global_issues_for_copy(
    *,
    markdown_cells: int,
    code_cells: int,
    executable_code_cells: int,
    response_cells: int,
    code_cells_not_executed: int,
    code_cells_with_errors: int,
) -> list[StudentGlobalIssue]:
    issues: list[StudentGlobalIssue] = []

    if markdown_cells == 0:
        issues.append(
            StudentGlobalIssue(
                severity="warning",
                kind="no_markdown_cells",
                message="aucune cellule Markdown détectée",
            )
        )

    if response_cells == 0:
        issues.append(
            StudentGlobalIssue(
                severity="warning",
                kind="no_response_zones",
                message="aucune zone « Réponse : » détectée",
            )
        )
        issues.append(
            StudentGlobalIssue(
                severity="info",
                kind="difficult_auto_correction",
                message="correction automatique difficile avec ce notebook",
            )
        )

    if executable_code_cells > 0 and code_cells_not_executed == executable_code_cells:
        issues.append(
            StudentGlobalIssue(
                severity="warning",
                kind="no_code_executed",
                message="aucune cellule de code non vide n'a été exécutée",
            )
        )
    elif code_cells_not_executed > 0:
        issues.append(
            StudentGlobalIssue(
                severity="warning",
                kind="some_code_not_executed",
                message="certaines cellules de code non vides n'ont pas été exécutées",
            )
        )

    if code_cells_with_errors > 0:
        issues.append(
            StudentGlobalIssue(
                severity="warning",
                kind="code_execution_errors",
                message="des erreurs d'exécution sont présentes",
            )
        )

    return issues


def _correction_readiness_for_copy(
    *,
    response_cells: int,
    empty_response_cells: int,
    result_cells: int,
    interpretation_cells: int,
    checklist_cells: int,
    headings: int,
    executable_code_cells: int,
    code_cells_not_executed: int,
    code_cells_with_errors: int,
) -> CorrectionReadiness:
    score = 0
    max_score = 6
    reasons: list[str] = []

    if response_cells > 0:
        score += 2
        reasons.append("zones « Réponse : » présentes")
    else:
        reasons.append("zones « Réponse : » absentes")

    if response_cells > 0 and empty_response_cells == 0:
        score += 1
        reasons.append("aucune réponse vide détectée")
    elif empty_response_cells > 0:
        reasons.append(f"{empty_response_cells} réponse(s) vide(s) ou à compléter")

    if result_cells > 0:
        score += 1
        reasons.append("cellules « Résultat » présentes")
    else:
        reasons.append("cellules « Résultat » absentes")

    if interpretation_cells > 0:
        score += 1
        reasons.append("cellules d'interprétation présentes")
    else:
        reasons.append("cellules d'interprétation absentes")

    if executable_code_cells == 0:
        reasons.append("aucune cellule de code non vide à vérifier")
    elif code_cells_with_errors > 0:
        reasons.append("erreurs d'exécution présentes")
    elif code_cells_not_executed > 0:
        reasons.append("certaines cellules de code non vides ne sont pas exécutées")
    else:
        score += 1
        reasons.append("code non vide exécuté sans erreur détectée")

    if checklist_cells > 0:
        reasons.append("checklist ou grille finale présente")

    if headings < 2:
        reasons.append("structure Markdown limitée")

    if score <= 1:
        level = "faible"
    elif score <= 3:
        level = "partielle"
    elif score <= 5:
        level = "bonne"
    else:
        level = "très bonne"

    return CorrectionReadiness(
        level=level,
        score=score,
        max_score=max_score,
        reasons=reasons,
    )


def _cell_text(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source)


def _count_markdown_headings(text: str) -> int:
    return sum(1 for line in text.splitlines() if re.match(r"^#{1,6}\s+", line.strip()))


def _contains_response_marker(text: str) -> bool:
    return re.search(r"réponse\s*:", text, flags=re.I) is not None


def _contains_result_marker(text: str) -> bool:
    return re.search(r"résultat\s*[—:-]|resultat\s*[—:-]", text, flags=re.I) is not None


def _contains_interpretation_marker(text: str) -> bool:
    return re.search(r"interpr[ée]tation|commentaire|analyse", text, flags=re.I) is not None


def _contains_checklist_marker(text: str) -> bool:
    return re.search(r"checklist|grille|évaluation|evaluation", text, flags=re.I) is not None


def _response_text(text: str) -> str:
    match = re.search(r"réponse\s*:", text, flags=re.I)
    if not match:
        return ""

    answer = text[match.end():]
    answer = re.sub(r"[*_`#>\-\s]+", " ", answer)
    return answer.strip(" .:\n\t")


def _is_empty_response(text: str) -> bool:
    answer = _response_text(text)
    if not answer:
        return True

    lowered = answer.lower()
    normalized = lowered.replace("é", "e").replace("è", "e").replace("ê", "e")

    placeholders = {
        "a completer",
        "à compléter",
        "todo",
        "reponse",
        "réponse",
        "...",
    }

    return lowered in placeholders or normalized in placeholders


def _is_short_response(text: str) -> bool:
    answer = _response_text(text)
    if not answer:
        return False

    words = re.findall(r"\w+", answer, flags=re.UNICODE)
    return len(words) <= 3


def _is_effectively_empty_code(source: str) -> bool:
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        return False
    return True


def _has_error_output(outputs: object) -> bool:
    if not isinstance(outputs, list):
        return False

    for output in outputs:
        if isinstance(output, dict) and output.get("output_type") == "error":
            return True

    return False


def _code_likely_expected_output(source: str) -> bool:
    lowered = source.lower()
    markers = [
        "print(",
        "plt.",
        ".plot(",
        "display(",
        "show(",
        "input(",
    ]
    return any(marker in lowered for marker in markers)


def _preview(text: str, max_length: int = 80) -> str:
    collapsed = " ".join(text.split())
    if not collapsed:
        return ""

    if len(collapsed) <= max_length:
        return collapsed

    return collapsed[: max_length - 1].rstrip() + "…"


def _severity_symbol(severity: str) -> str:
    if severity == "warning":
        return "⚠"
    if severity == "info":
        return "ℹ"
    return "•"
