from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

import nbformat

from tpstudio.code_semantics import analyze_code_semantics


RELATIVE_ERROR_THRESHOLD = 0.15


@dataclass(frozen=True)
class NumericalConsistencyFinding:
    code_cell_index: int
    response_cell_index: int | None
    section_title: str
    target: str
    code_value: float
    expected_value: float
    relative_error: float
    reference_kind: str
    message: str
    copy_code_source: str
    response_anchor: str

    @property
    def relative_error_percent(self) -> float:
        return 100.0 * self.relative_error


def analyze_numerical_consistency(
    model_path: str | Path,
    copy_path: str | Path,
) -> list[NumericalConsistencyFinding]:
    model = nbformat.read(Path(model_path), as_version=4)
    copy = nbformat.read(Path(copy_path), as_version=4)

    return analyze_numerical_consistency_in_notebooks(
        model,
        copy,
        model_path=model_path,
        copy_path=copy_path,
    )


def analyze_numerical_consistency_in_notebooks(
    model,
    copy,
    *,
    model_path: str | Path | None = None,
    copy_path: str | Path | None = None,
) -> list[NumericalConsistencyFinding]:
    section_titles = _top_level_sections(copy)
    copy_results = _copy_result_cells(copy, section_titles)

    model_references: dict[int, tuple[str, float]] = {}

    if model_path is not None and copy_path is not None:
        for semantic_finding in analyze_code_semantics(
            model_path,
            copy_path,
        ):
            model_value = _main_result_value(
                model.cells[semantic_finding.model_cell_index]
            )
            copy_value = _main_result_value(
                copy.cells[semantic_finding.copy_cell_index]
            )

            if model_value is None or copy_value is None:
                continue

            model_references[
                semantic_finding.copy_cell_index
            ] = (
                semantic_finding.target,
                model_value,
            )

    findings: list[NumericalConsistencyFinding] = []

    for result in copy_results:
        code_cell_index = result["cell_index"]
        code_value = result["value"]

        model_reference = model_references.get(code_cell_index)

        response_reference = _find_following_response_reference(
            copy,
            code_cell_index=code_cell_index,
            section_title=result["section_title"],
            preferred_value=(
                model_reference[1]
                if model_reference is not None
                else code_value
            ),
            section_titles=section_titles,
        )

        expected_value = None
        target = ""
        reference_kind = ""
        response_cell_index = None
        response_anchor = ""

        if model_reference is not None and response_reference is not None:
            model_target, model_value = model_reference
            response_value = response_reference["value"]

            if _values_are_close(
                model_value,
                response_value,
                tolerance=0.10,
            ):
                expected_value = model_value
                target = model_target
                reference_kind = "model_and_written"
                response_cell_index = response_reference["cell_index"]
                response_anchor = response_reference["anchor"]

        if expected_value is None and response_reference is not None:
            expected_value = response_reference["value"]
            reference_kind = "written"
            response_cell_index = response_reference["cell_index"]
            response_anchor = response_reference["anchor"]

        if expected_value is None and model_reference is not None:
            target, expected_value = model_reference
            reference_kind = "model"

        if expected_value is None:
            continue

        relative_error = _relative_error(
            code_value,
            expected_value,
        )

        if relative_error <= RELATIVE_ERROR_THRESHOLD:
            continue

        if reference_kind == "model_and_written":
            message = (
                "Le résultat réellement calculé ne correspond ni à la "
                "valeur du corrigé ni à la valeur annoncée dans le texte."
            )
        elif reference_kind == "written":
            message = (
                "Le résultat réellement calculé ne correspond pas à la "
                "valeur annoncée dans le texte."
            )
        else:
            message = (
                "Le résultat réellement calculé diffère fortement de la "
                "valeur obtenue dans le corrigé."
            )

        findings.append(
            NumericalConsistencyFinding(
                code_cell_index=code_cell_index,
                response_cell_index=response_cell_index,
                section_title=result["section_title"],
                target=target,
                code_value=code_value,
                expected_value=expected_value,
                relative_error=relative_error,
                reference_kind=reference_kind,
                message=message,
                copy_code_source=result["source"],
                response_anchor=response_anchor,
            )
        )

    return _deduplicate_findings(findings)


def add_numerical_consistency_feedback_to_notebook(
    model_path: str | Path,
    copy_path: str | Path,
    corrected_path: str | Path,
) -> int:
    findings = analyze_numerical_consistency(
        model_path,
        copy_path,
    )

    if not findings:
        return 0

    corrected = Path(corrected_path)
    notebook = nbformat.read(corrected, as_version=4)

    inserted = 0

    for finding in reversed(findings):
        target_index = None

        if finding.response_anchor:
            target_index = _find_response_anchor_index(
                notebook,
                finding.response_anchor,
            )

        if target_index is None:
            target_index = _find_matching_code_cell_index(
                notebook,
                finding.copy_code_source,
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
            "kind": "numerical-consistency-feedback",
            "status": "probable-error",
        }

        notebook.cells.insert(target_index + 1, comment)
        inserted += 1

    if inserted:
        nbformat.write(notebook, corrected)

    return inserted


def add_numerical_consistency_feedback_to_report(
    model_path: str | Path,
    copy_path: str | Path,
    report_path: str | Path,
) -> int:
    findings = analyze_numerical_consistency(
        model_path,
        copy_path,
    )

    if not findings:
        return 0

    report = Path(report_path)
    text = report.read_text(encoding="utf-8")

    if "### Cohérence des résultats numériques" in text:
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


def _copy_result_cells(
    notebook,
    section_titles: list[str],
) -> list[dict]:
    results: list[dict] = []

    for cell_index, cell in enumerate(notebook.cells):
        if getattr(cell, "cell_type", "") != "code":
            continue

        value = _main_result_value(cell)

        if value is None:
            continue

        results.append(
            {
                "cell_index": cell_index,
                "section_title": section_titles[cell_index],
                "value": value,
                "source": str(
                    getattr(cell, "source", "") or ""
                ),
            }
        )

    return results


def _main_result_value(cell) -> float | None:
    if getattr(cell, "cell_type", "") != "code":
        return None

    output_text = _cell_output_text(cell)

    if not output_text.strip():
        return None

    for line in output_text.splitlines():
        normalized = _normalize(line)

        if not normalized:
            continue

        if any(
            excluded in normalized
            for excluded in (
                "incertitude",
                "ecart normalise",
                "ecart-type",
                "ecart type",
                "standard deviation",
                "std",
            )
        ):
            continue

        if any(
            label in normalized
            for label in (
                "meilleur estimateur",
                "valeur moyenne",
                "moyenne obtenue",
                "resultat obtenu",
                "resultat :",
            )
        ):
            values = _extract_numbers(line)

            if values:
                return values[-1]

    stripped = output_text.strip()

    if re.fullmatch(
        r"[-+]?(?:\d+(?:[.,]\d*)?|[.,]\d+)"
        r"(?:[eE][-+]?\d+)?",
        stripped,
    ):
        values = _extract_numbers(stripped)

        if values:
            return values[0]

    return None


def _cell_output_text(cell) -> str:
    parts: list[str] = []

    for output in getattr(cell, "outputs", []) or []:
        output_type = output.get("output_type", "")

        if output_type == "stream":
            text = output.get("text", "")
            parts.append(
                "".join(text)
                if isinstance(text, list)
                else str(text)
            )
            continue

        data = output.get("data", {}) or {}
        plain = data.get("text/plain")

        if plain is not None:
            parts.append(
                "".join(plain)
                if isinstance(plain, list)
                else str(plain)
            )

    return "\n".join(parts)


def _top_level_sections(notebook) -> list[str]:
    sections: list[str] = []
    current = ""

    for cell in notebook.cells:
        if getattr(cell, "cell_type", "") == "markdown":
            source = str(getattr(cell, "source", "") or "")
            heading = _first_h1(source)

            if heading:
                current = heading

        sections.append(current)

    return sections


def _first_h1(source: str) -> str:
    match = re.search(
        r"(?m)^\s*#\s+(.+?)\s*$",
        source,
    )

    if not match:
        return ""

    return match.group(1).strip().rstrip(":")


def _find_following_response_reference(
    notebook,
    *,
    code_cell_index: int,
    section_title: str,
    preferred_value: float,
    section_titles: list[str],
) -> dict | None:
    candidates: list[dict] = []

    for cell_index in range(
        code_cell_index + 1,
        len(notebook.cells),
    ):
        if (
            section_titles[cell_index]
            and section_titles[cell_index] != section_title
        ):
            break

        cell = notebook.cells[cell_index]

        if getattr(cell, "cell_type", "") != "markdown":
            continue

        source = str(getattr(cell, "source", "") or "")

        if "reponse" not in _normalize(source):
            continue

        values = _response_result_values(source)

        for value in values:
            candidates.append(
                {
                    "cell_index": cell_index,
                    "value": value,
                    "anchor": _response_anchor(source),
                }
            )

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda candidate: abs(
            candidate["value"] - preferred_value
        ),
    )


def _response_result_values(source: str) -> list[float]:
    plain = re.sub(r"<[^>]+>", " ", source)
    plain = re.sub(r"[*_`#]+", " ", plain)
    plain = re.sub(r"\s+", " ", plain)

    values: list[float] = []

    for sentence in re.split(r"(?<=[.!?])\s+", plain):
        normalized = _normalize(sentence)

        if not normalized:
            continue

        if any(
            excluded in normalized
            for excluded in (
                "ecart normalise",
                "incertitude",
                "inferieur a",
                "superieur a",
                "seuil",
            )
        ):
            continue

        if not any(
            keyword in normalized
            for keyword in (
                "indice",
                "valeur",
                "mesure",
                "resultat",
                "vaut",
                "obtient",
                "autour de",
                "proche de",
                "voisin de",
            )
        ):
            continue

        values.extend(_extract_numbers(sentence))

    return values


def _response_anchor(source: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", source)
    plain = re.sub(r"[*_`#]+", " ", plain)
    plain = re.sub(r"\s+", " ", plain).strip()

    normalized = _normalize(plain)
    marker = "reponse"

    position = normalized.find(marker)

    if position != -1:
        normalized = normalized[position + len(marker):].strip(" :")

    return normalized[:120]


def _find_response_anchor_index(
    notebook,
    anchor: str,
) -> int | None:
    if not anchor:
        return None

    for index, cell in enumerate(notebook.cells):
        if getattr(cell, "cell_type", "") != "markdown":
            continue

        source = str(getattr(cell, "source", "") or "")
        normalized = _normalize(
            re.sub(r"<[^>]+>", " ", source)
        )

        if anchor in normalized:
            return index

    return None


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


def _extract_numbers(text: str) -> list[float]:
    matches = re.findall(
        r"(?<![\w.])"
        r"[-+]?(?:\d+(?:[.,]\d*)?|[.,]\d+)"
        r"(?:[eE][-+]?\d+)?",
        text,
    )

    values: list[float] = []

    for match in matches:
        try:
            values.append(
                float(match.replace(",", "."))
            )
        except ValueError:
            continue

    return values


def _relative_error(
    value: float,
    reference: float,
) -> float:
    denominator = max(abs(reference), 1e-12)
    return abs(value - reference) / denominator


def _values_are_close(
    first: float,
    second: float,
    *,
    tolerance: float,
) -> bool:
    return _relative_error(first, second) <= tolerance


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    without_accents = "".join(
        char
        for char in normalized
        if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_accents.casefold().split())


def _deduplicate_findings(
    findings: list[NumericalConsistencyFinding],
) -> list[NumericalConsistencyFinding]:
    seen: set[tuple[int, float, float]] = set()
    result: list[NumericalConsistencyFinding] = []

    for finding in findings:
        key = (
            finding.code_cell_index,
            round(finding.code_value, 9),
            round(finding.expected_value, 9),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(finding)

    return result


def _feedback_marker(
    finding: NumericalConsistencyFinding,
) -> str:
    return (
        "Retour TPStudio — cohérence numérique — "
        f"{finding.code_cell_index}"
    )


def _comment_already_present(
    notebook,
    marker: str,
) -> bool:
    return any(
        marker in str(getattr(cell, "source", "") or "")
        for cell in notebook.cells
    )


def _format_number(value: float) -> str:
    return f"{value:.4g}"


def _format_local_feedback(
    finding: NumericalConsistencyFinding,
) -> str:
    marker = _feedback_marker(finding)
    context = (
        f" — {finding.section_title}"
        if finding.section_title
        else ""
    )

    return f"""
<div style="background:#ffebee; border-left:5px solid #c62828; padding:12px 14px; border-radius:6px;">

### Retour TPStudio — cohérence numérique{context}

**Écart important entre le calcul et le résultat attendu.**

{finding.message}

- **Valeur réellement calculée :** `{_format_number(finding.code_value)}`
- **Valeur attendue ou annoncée :** `{_format_number(finding.expected_value)}`
- **Écart relatif :** `{finding.relative_error_percent:.0f} %`

Vérifiez la formule, puis relancez le notebook et mettez à jour le commentaire écrit.

</div>

<!-- {marker} -->
""".strip()


def _format_report_section(
    findings: list[NumericalConsistencyFinding],
) -> str:
    lines = [
        "### Cohérence des résultats numériques",
        (
            "- Résultats numériques incompatibles : "
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
            f"- ❌ Cellule {finding.code_cell_index + 1}"
            f"{context} : valeur calculée "
            f"`{_format_number(finding.code_value)}` au lieu de "
            f"`{_format_number(finding.expected_value)}` "
            f"(écart relatif {finding.relative_error_percent:.0f} %)."
        )
        lines.append(
            f"  - {finding.message}"
        )

    return "\n".join(lines)


def _insert_summary_line(
    text: str,
    *,
    finding_count: int,
) -> str:
    label = "- Résultats numériques incompatibles : "
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
    findings: list[NumericalConsistencyFinding],
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
            f"- Cellule {finding.code_cell_index + 1}"
            f"{context} — incohérence numérique : "
            f"`{_format_number(finding.code_value)}` calculé contre "
            f"`{_format_number(finding.expected_value)}` attendu ou annoncé."
        )

        if bullet not in text:
            additions.append(bullet)

    if not additions:
        return text

    insertion = "\n" + "\n".join(additions)
    return text[:line_end] + insertion + text[line_end:]


def _insert_advice(text: str) -> str:
    advice = (
        "- Vérifiez que les valeurs commentées dans le texte correspondent "
        "réellement aux dernières sorties du code."
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
