from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

import nbformat


@dataclass(frozen=True)
class CodeCellRecord:
    cell_index: int
    code_ordinal: int
    section_title: str
    section_ordinal: int
    source: str


@dataclass(frozen=True)
class CodeSemanticFinding:
    model_cell_index: int
    copy_cell_index: int
    section_title: str
    target: str
    kind: str
    message: str
    model_expression: str
    copy_expression: str
    copy_source: str


def analyze_code_semantics(
    model_path: str | Path,
    copy_path: str | Path,
) -> list[CodeSemanticFinding]:
    model = nbformat.read(Path(model_path), as_version=4)
    copy = nbformat.read(Path(copy_path), as_version=4)

    return analyze_code_semantics_in_notebooks(model, copy)


def analyze_code_semantics_in_notebooks(
    model,
    copy,
) -> list[CodeSemanticFinding]:
    model_records = _code_cell_records(model)
    copy_records = _code_cell_records(copy)

    model_assignments = _assignment_occurrences(model_records)
    copy_assignments = _assignment_occurrences(copy_records)

    findings: list[CodeSemanticFinding] = []

    for target in sorted(
        set(model_assignments) & set(copy_assignments)
    ):
        pairs = _align_assignment_occurrences(
            model_assignments[target],
            copy_assignments[target],
        )

        for (model_record, model_value), (
            copy_record,
            copy_value,
        ) in pairs:
            finding = _compare_assignment_expressions(
                target=target,
                model_value=model_value,
                copy_value=copy_value,
                model_record=model_record,
                copy_record=copy_record,
            )

            if finding is not None:
                findings.append(finding)

    return _deduplicate_findings(findings)

def add_code_semantic_feedback_to_notebook(
    model_path: str | Path,
    copy_path: str | Path,
    corrected_path: str | Path,
) -> int:
    findings = analyze_code_semantics(model_path, copy_path)

    if not findings:
        return 0

    corrected = Path(corrected_path)
    notebook = nbformat.read(corrected, as_version=4)

    inserted = 0

    for finding in reversed(findings):
        target_index = _find_matching_code_cell_index(
            notebook,
            finding.copy_source,
        )

        if target_index is None:
            continue

        marker = _feedback_marker(finding)

        if _comment_already_present(notebook, marker):
            continue

        comment = nbformat.v4.new_markdown_cell(
            _format_local_feedback(finding)
        )
        comment.metadata["tpstudio"] = {
            "kind": "code-semantic-feedback",
            "target": finding.target,
            "finding_kind": finding.kind,
        }

        notebook.cells.insert(target_index + 1, comment)
        inserted += 1

    if inserted:
        nbformat.write(notebook, corrected)

    return inserted


def add_code_semantic_feedback_to_report(
    model_path: str | Path,
    copy_path: str | Path,
    report_path: str | Path,
) -> int:
    findings = analyze_code_semantics(model_path, copy_path)

    if not findings:
        return 0

    report = Path(report_path)
    text = report.read_text(encoding="utf-8")

    if "### Diagnostic sémantique du code" in text:
        return len(findings)

    section = _format_report_section(findings)

    anchor = "### Diagnostic des graphes"

    if anchor in text:
        text = text.replace(
            anchor,
            section + "\n\n" + anchor,
            1,
        )
    else:
        text = text.rstrip() + "\n\n" + section + "\n"

    text = _insert_summary_line(
        text,
        finding_count=len(findings),
    )
    text = _increment_local_comment_count(
        text,
        increment=len(findings),
    )
    text = _insert_priorities(text, findings)
    text = _insert_advice(text)

    report.write_text(text, encoding="utf-8")
    return len(findings)


def _assignment_occurrences(
    records: list[CodeCellRecord],
) -> dict[str, list[tuple[CodeCellRecord, ast.AST]]]:
    occurrences: dict[
        str,
        list[tuple[CodeCellRecord, ast.AST]],
    ] = {}

    for record in records:
        try:
            tree = ast.parse(record.source)
        except SyntaxError:
            continue

        assignments = _extract_assignments(tree)

        for target, values in assignments.items():
            for value in values:
                occurrences.setdefault(target, []).append(
                    (record, value)
                )

    return occurrences


def _align_assignment_occurrences(
    model_items: list[tuple[CodeCellRecord, ast.AST]],
    copy_items: list[tuple[CodeCellRecord, ast.AST]],
) -> list[
    tuple[
        tuple[CodeCellRecord, ast.AST],
        tuple[CodeCellRecord, ast.AST],
    ]
]:
    """Align same-target assignments by semantic similarity.

    This deliberately ignores notebook cell boundaries. A model cell may be
    split into several student cells, or several model cells may be merged.
    Only high-confidence expression matches are retained.
    """

    candidates: list[
        tuple[
            int,
            int,
            int,
            int,
        ]
    ] = []

    for model_index, model_item in enumerate(model_items):
        for copy_index, copy_item in enumerate(copy_items):
            score = _assignment_match_score(
                model_item,
                copy_item,
                model_index=model_index,
                copy_index=copy_index,
            )

            if score < 80:
                continue

            candidates.append(
                (
                    score,
                    -abs(model_index - copy_index),
                    model_index,
                    copy_index,
                )
            )

    candidates.sort(reverse=True)

    used_model: set[int] = set()
    used_copy: set[int] = set()
    pairs = []

    for _, _, model_index, copy_index in candidates:
        if model_index in used_model:
            continue

        if copy_index in used_copy:
            continue

        used_model.add(model_index)
        used_copy.add(copy_index)

        pairs.append(
            (
                model_items[model_index],
                copy_items[copy_index],
            )
        )

    return sorted(
        pairs,
        key=lambda pair: pair[1][0].cell_index,
    )


def _assignment_match_score(
    model_item: tuple[CodeCellRecord, ast.AST],
    copy_item: tuple[CodeCellRecord, ast.AST],
    *,
    model_index: int,
    copy_index: int,
) -> int:
    model_record, model_value = model_item
    copy_record, copy_value = copy_item

    if _same_ast(model_value, copy_value):
        score = 120
    elif _is_swapped_quotient(model_value, copy_value):
        score = 110
    else:
        changed_constants = _numeric_constant_differences(
            model_value,
            copy_value,
        )

        if changed_constants is not None and changed_constants:
            score = 105
        elif _changed_binary_operator(
            model_value,
            copy_value,
        ) is not None:
            score = 100
        else:
            score = _expression_shape_score(
                model_value,
                copy_value,
            )

    if (
        _normalize(model_record.section_title)
        and _normalize(model_record.section_title)
        == _normalize(copy_record.section_title)
    ):
        score += 10

    score -= min(
        abs(model_index - copy_index),
        5,
    )

    return score


def _expression_shape_score(
    model_value: ast.AST,
    copy_value: ast.AST,
) -> int:
    """Conservative fallback used only for pairing, never for flagging."""

    if type(model_value) is not type(copy_value):
        return 0

    model_names = _expression_names(model_value)
    copy_names = _expression_names(copy_value)

    if not model_names or not copy_names:
        return 0

    common = model_names & copy_names
    union = model_names | copy_names

    similarity = len(common) / len(union)

    if similarity < 0.75:
        return 0

    model_ops = _operator_types(model_value)
    copy_ops = _operator_types(copy_value)

    if model_ops != copy_ops:
        return 0

    return 80


def _expression_names(node: ast.AST) -> set[str]:
    names: set[str] = set()

    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(_call_name(child))

    return {
        name
        for name in names
        if name
    }


def _operator_types(node: ast.AST) -> tuple[str, ...]:
    return tuple(
        type(child).__name__
        for child in ast.walk(node)
        if isinstance(
            child,
            (
                ast.operator,
                ast.unaryop,
                ast.boolop,
                ast.cmpop,
            ),
        )
    )


def _code_cell_records(notebook) -> list[CodeCellRecord]:
    records: list[CodeCellRecord] = []
    current_section = ""
    section_counts: dict[str, int] = {}
    code_ordinal = 0

    for cell_index, cell in enumerate(notebook.cells):
        cell_type = getattr(cell, "cell_type", "")
        source = str(getattr(cell, "source", "") or "")

        if cell_type == "markdown":
            heading = _last_heading(source)
            if heading:
                current_section = heading
            continue

        if cell_type != "code":
            continue

        normalized_section = _normalize(current_section)
        section_ordinal = section_counts.get(normalized_section, 0)
        section_counts[normalized_section] = section_ordinal + 1

        records.append(
            CodeCellRecord(
                cell_index=cell_index,
                code_ordinal=code_ordinal,
                section_title=current_section,
                section_ordinal=section_ordinal,
                source=source,
            )
        )
        code_ordinal += 1

    return records


def _align_code_cells(
    model_records: list[CodeCellRecord],
    copy_records: list[CodeCellRecord],
) -> list[tuple[CodeCellRecord, CodeCellRecord]]:
    model_by_key = {
        (_normalize(record.section_title), record.section_ordinal): record
        for record in model_records
    }
    copy_by_key = {
        (_normalize(record.section_title), record.section_ordinal): record
        for record in copy_records
    }

    pairs: list[tuple[CodeCellRecord, CodeCellRecord]] = []
    used_model: set[int] = set()
    used_copy: set[int] = set()

    for key, model_record in model_by_key.items():
        copy_record = copy_by_key.get(key)

        if copy_record is None:
            continue

        pairs.append((model_record, copy_record))
        used_model.add(model_record.code_ordinal)
        used_copy.add(copy_record.code_ordinal)

    model_by_ordinal = {
        record.code_ordinal: record
        for record in model_records
        if record.code_ordinal not in used_model
    }
    copy_by_ordinal = {
        record.code_ordinal: record
        for record in copy_records
        if record.code_ordinal not in used_copy
    }

    for ordinal in sorted(
        set(model_by_ordinal) & set(copy_by_ordinal)
    ):
        pairs.append(
            (
                model_by_ordinal[ordinal],
                copy_by_ordinal[ordinal],
            )
        )

    return sorted(
        pairs,
        key=lambda pair: pair[1].cell_index,
    )


def _compare_code_cell_pair(
    model_record: CodeCellRecord,
    copy_record: CodeCellRecord,
) -> list[CodeSemanticFinding]:
    try:
        model_tree = ast.parse(model_record.source)
        copy_tree = ast.parse(copy_record.source)
    except SyntaxError:
        return []

    model_assignments = _extract_assignments(model_tree)
    copy_assignments = _extract_assignments(copy_tree)

    findings: list[CodeSemanticFinding] = []

    for target in sorted(
        set(model_assignments) & set(copy_assignments)
    ):
        model_values = model_assignments[target]
        copy_values = copy_assignments[target]

        for model_value, copy_value in zip(
            model_values,
            copy_values,
        ):
            finding = _compare_assignment_expressions(
                target=target,
                model_value=model_value,
                copy_value=copy_value,
                model_record=model_record,
                copy_record=copy_record,
            )

            if finding is not None:
                findings.append(finding)

    return findings


def _extract_assignments(
    tree: ast.AST,
) -> dict[str, list[ast.AST]]:
    assignments: dict[str, list[ast.AST]] = {}

    class Visitor(ast.NodeVisitor):
        def visit_Assign(self, node: ast.Assign) -> None:
            for target_node in node.targets:
                target = _simple_target_name(target_node)

                if target is not None:
                    assignments.setdefault(target, []).append(node.value)

            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            target = _simple_target_name(node.target)

            if target is not None and node.value is not None:
                assignments.setdefault(target, []).append(node.value)

            self.generic_visit(node)

    Visitor().visit(tree)
    return assignments


def _simple_target_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id

    return None


def _compare_assignment_expressions(
    *,
    target: str,
    model_value: ast.AST,
    copy_value: ast.AST,
    model_record: CodeCellRecord,
    copy_record: CodeCellRecord,
) -> CodeSemanticFinding | None:
    if _same_ast(model_value, copy_value):
        return None

    if _is_data_container_expression(
        model_value
    ) or _is_data_container_expression(copy_value):
        return None

    if _is_swapped_quotient(model_value, copy_value):
        return _finding(
            target=target,
            kind="swapped_quotient",
            message=(
                "Les termes du quotient semblent inversés par rapport "
                "au corrigé."
            ),
            model_value=model_value,
            copy_value=copy_value,
            model_record=model_record,
            copy_record=copy_record,
        )

    changed_constants = _numeric_constant_differences(
        model_value,
        copy_value,
    )

    if changed_constants is not None and changed_constants:
        if len(changed_constants) <= 3 and _is_formula_like(model_value):
            details = ", ".join(
                f"{copy_number} au lieu de {model_number}"
                for model_number, copy_number in changed_constants
            )

            return _finding(
                target=target,
                kind="changed_constant",
                message=(
                    "La formule conserve la même structure que le corrigé, "
                    f"mais une constante numérique diffère ({details})."
                ),
                model_value=model_value,
                copy_value=copy_value,
                model_record=model_record,
                copy_record=copy_record,
            )

    operator_change = _changed_binary_operator(
        model_value,
        copy_value,
    )

    if operator_change is not None:
        model_operator, copy_operator = operator_change

        return _finding(
            target=target,
            kind="changed_operator",
            message=(
                "L'opérateur utilisé dans la formule diffère du corrigé "
                f"({copy_operator} au lieu de {model_operator})."
            ),
            model_value=model_value,
            copy_value=copy_value,
            model_record=model_record,
            copy_record=copy_record,
        )

    return None


def _finding(
    *,
    target: str,
    kind: str,
    message: str,
    model_value: ast.AST,
    copy_value: ast.AST,
    model_record: CodeCellRecord,
    copy_record: CodeCellRecord,
) -> CodeSemanticFinding:
    return CodeSemanticFinding(
        model_cell_index=model_record.cell_index,
        copy_cell_index=copy_record.cell_index,
        section_title=copy_record.section_title,
        target=target,
        kind=kind,
        message=message,
        model_expression=_safe_unparse(model_value),
        copy_expression=_safe_unparse(copy_value),
        copy_source=copy_record.source,
    )


def _is_swapped_quotient(
    model_value: ast.AST,
    copy_value: ast.AST,
) -> bool:
    if not (
        isinstance(model_value, ast.BinOp)
        and isinstance(copy_value, ast.BinOp)
        and isinstance(model_value.op, ast.Div)
        and isinstance(copy_value.op, ast.Div)
    ):
        return False

    return (
        _same_ast(model_value.left, copy_value.right)
        and _same_ast(model_value.right, copy_value.left)
    )


def _numeric_constant_differences(
    model_node: ast.AST,
    copy_node: ast.AST,
) -> list[tuple[str, str]] | None:
    differences: list[tuple[str, str]] = []

    def compare(left, right) -> bool:
        if type(left) is not type(right):
            return False

        if isinstance(left, ast.Constant):
            if _is_number(left.value) and _is_number(right.value):
                if left.value != right.value:
                    differences.append(
                        (str(left.value), str(right.value))
                    )
                return True

            return left.value == right.value

        if isinstance(left, ast.AST):
            for field in left._fields:
                left_value = getattr(left, field)
                right_value = getattr(right, field)

                if not compare(left_value, right_value):
                    return False

            return True

        if isinstance(left, list):
            if len(left) != len(right):
                return False

            return all(
                compare(left_item, right_item)
                for left_item, right_item in zip(left, right)
            )

        return left == right

    if compare(model_node, copy_node):
        return differences

    return None


def _changed_binary_operator(
    model_value: ast.AST,
    copy_value: ast.AST,
) -> tuple[str, str] | None:
    if not (
        isinstance(model_value, ast.BinOp)
        and isinstance(copy_value, ast.BinOp)
    ):
        return None

    if type(model_value.op) is type(copy_value.op):
        return None

    if not (
        _same_ast(model_value.left, copy_value.left)
        and _same_ast(model_value.right, copy_value.right)
    ):
        return None

    return (
        _operator_symbol(model_value.op),
        _operator_symbol(copy_value.op),
    )


def _operator_symbol(operator: ast.operator) -> str:
    symbols = {
        ast.Add: "+",
        ast.Sub: "-",
        ast.Mult: "*",
        ast.Div: "/",
        ast.Pow: "**",
        ast.Mod: "%",
        ast.FloorDiv: "//",
    }

    return symbols.get(type(operator), type(operator).__name__)


def _is_formula_like(node: ast.AST) -> bool:
    return any(
        isinstance(child, (ast.BinOp, ast.UnaryOp, ast.Call))
        for child in ast.walk(node)
    )


def _is_data_container_expression(node: ast.AST) -> bool:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return True

    if isinstance(node, ast.Call):
        function_name = _call_name(node.func)

        if function_name in {
            "array",
            "np.array",
            "numpy.array",
            "asarray",
            "np.asarray",
            "numpy.asarray",
        }:
            return True

    return False


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)

        if prefix:
            return f"{prefix}.{node.attr}"

        return node.attr

    return ""


def _same_ast(left: ast.AST, right: ast.AST) -> bool:
    return ast.dump(
        left,
        include_attributes=False,
    ) == ast.dump(
        right,
        include_attributes=False,
    )


def _safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ast.dump(
            node,
            include_attributes=False,
        )


def _is_number(value) -> bool:
    return isinstance(value, (int, float, complex)) and not isinstance(
        value,
        bool,
    )


def _last_heading(source: str) -> str:
    matches = re.findall(
        r"(?m)^\s{0,3}#{1,6}\s*(.+?)\s*$",
        source,
    )

    if not matches:
        return ""

    return matches[-1].strip().rstrip(":")


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    without_accents = "".join(
        char
        for char in normalized
        if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_accents.casefold().split())


def _deduplicate_findings(
    findings: list[CodeSemanticFinding],
) -> list[CodeSemanticFinding]:
    seen: set[tuple[int, str, str, str, str]] = set()
    result: list[CodeSemanticFinding] = []

    for finding in findings:
        key = (
            finding.copy_cell_index,
            finding.target,
            finding.kind,
            finding.model_expression,
            finding.copy_expression,
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(finding)

    return result


def _find_matching_code_cell_index(
    notebook,
    source_text: str,
) -> int | None:
    target = source_text.strip()

    for index, cell in enumerate(notebook.cells):
        if getattr(cell, "cell_type", "") != "code":
            continue

        if str(getattr(cell, "source", "") or "").strip() == target:
            return index

    return None


def _feedback_marker(
    finding: CodeSemanticFinding,
) -> str:
    return (
        "Retour TPStudio — code sémantique — "
        f"{finding.copy_cell_index} — {finding.target} — {finding.kind}"
    )


def _comment_already_present(
    notebook,
    marker: str,
) -> bool:
    return any(
        marker in str(getattr(cell, "source", "") or "")
        for cell in notebook.cells
    )


def _format_local_feedback(
    finding: CodeSemanticFinding,
) -> str:
    marker = _feedback_marker(finding)
    context = (
        f" — {finding.section_title}"
        if finding.section_title
        else ""
    )

    return f"""
<div style="background:#fff0e0; border-left:5px solid #ef6c00; padding:12px 14px; border-radius:6px;">

### Code à vérifier{context}

**Variable concernée :** `{finding.target}`

{finding.message}

- **Corrigé :** `{finding.target} = {finding.model_expression}`
- **Copie :** `{finding.target} = {finding.copy_expression}`

Vérifiez la formule physique avant de valider ce calcul.

</div>

<!-- {marker} -->
""".strip()


def _format_report_section(
    findings: list[CodeSemanticFinding],
) -> str:
    lines = [
        "### Diagnostic sémantique du code",
        (
            "- Écarts sémantiques à vérifier : "
            f"**{len(findings)}**."
        ),
    ]

    for finding in findings:
        context = (
            f" — partie « {finding.section_title} »"
            if finding.section_title
            else ""
        )

        lines.append(
            f"- ⚠️ Cellule {finding.copy_cell_index + 1}"
            f"{context} — variable `{finding.target}` : "
            f"{finding.message}"
        )
        lines.append(
            f"  - Corrigé : `{finding.target} = "
            f"{finding.model_expression}`"
        )
        lines.append(
            f"  - Copie : `{finding.target} = "
            f"{finding.copy_expression}`"
        )

    return "\n".join(lines)


def _insert_summary_line(
    text: str,
    *,
    finding_count: int,
) -> str:
    label = "- Écarts sémantiques de code à vérifier : "
    line = f"{label}**{finding_count}**."

    if label in text:
        return text

    anchor_pattern = re.compile(
        r"^- Commentaires locaux insérés : \*\*\d+\*\*\.\s*$",
        re.MULTILINE,
    )
    match = anchor_pattern.search(text)

    if match:
        return text[:match.start()] + line + "\n" + text[match.start():]

    return text


def _increment_local_comment_count(
    text: str,
    *,
    increment: int,
) -> str:
    if increment <= 0:
        return text

    pattern = re.compile(
        r"(- Commentaires locaux insérés : \*\*)(\d+)(\*\*\.)"
    )

    def replace(match: re.Match[str]) -> str:
        current = int(match.group(2))
        return (
            match.group(1)
            + str(current + increment)
            + match.group(3)
        )

    return pattern.sub(replace, text, count=1)


def _insert_priorities(
    text: str,
    findings: list[CodeSemanticFinding],
) -> str:
    if not findings:
        return text

    header = "### Priorités avant nouveau rendu"
    position = text.find(header)

    if position == -1:
        return text

    line_end = text.find("\n", position)

    if line_end == -1:
        return text

    additions: list[str] = []

    for finding in findings:
        context = (
            f" — partie « {finding.section_title} »"
            if finding.section_title
            else ""
        )

        bullet = (
            f"- Cellule {finding.copy_cell_index + 1}"
            f"{context} — code à vérifier pour `{finding.target}` : "
            f"{finding.message}"
        )

        if bullet not in text:
            additions.append(bullet)

    if not additions:
        return text

    insertion = "\n" + "\n".join(additions)
    return text[:line_end] + insertion + text[line_end:]


def _insert_advice(text: str) -> str:
    advice = (
        "- Vérifiez les formules de code signalées comme différentes "
        "du corrigé."
    )

    if advice in text:
        return text

    header = "### Conseils ciblés"
    position = text.find(header)

    if position == -1:
        return text

    line_end = text.find("\n", position)

    if line_end == -1:
        return text

    return text[:line_end] + "\n" + advice + text[line_end:]
