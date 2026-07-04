from __future__ import annotations
from tpstudio.code_semantics import add_code_semantic_feedback_to_notebook
from tpstudio.pedagogical_sections import add_pedagogical_section_feedback_to_notebook

import copy
import json
import re
from pathlib import Path

from tpstudio.copy_comparison import (
    CopyComparison,
    compare_copy_to_model,
)
from tpstudio.graph_comparison import (
    GraphComparison,
    compare_graphs,
)
from tpstudio.response_diagnostics import (
    ResponseDiagnosis,
    diagnose_responses_from_notebook,
)


def _tpstudio_original_create_feedback_notebook_a61a(
    model_path: str | Path,
    copy_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """Create a non-destructive notebook copy with TPStudio feedback inserted.

    The original student notebook is never modified. The generated copy contains:
    - a compact structured summary cell at the beginning;
    - local Markdown comments after cells that need attention;
    - readable diagnostics for every student response;
    - graph diagnostics when matplotlib graphs differ from the model.
    """

    model = Path(model_path)
    source = Path(copy_path)

    if output_path is None:
        output = _next_available_feedback_path(source)
    else:
        output = Path(output_path)

    comparison = compare_copy_to_model(model, source)

    data = json.loads(source.read_text(encoding="utf-8"))
    updated = copy.deepcopy(data)

    original_cells = updated.setdefault("cells", [])
    if not isinstance(original_cells, list):
        original_cells = []

    colored_cells = _color_response_cells(original_cells, comparison)
    updated["cells"] = _cells_with_feedback(colored_cells, comparison)

    metadata = updated.setdefault("metadata", {})
    if isinstance(metadata, dict):
        tpstudio_metadata = metadata.setdefault("tpstudio", {})
        if isinstance(tpstudio_metadata, dict):
            tpstudio_metadata["feedback_inserted"] = True
            tpstudio_metadata["feedback_source_model"] = model.name
            tpstudio_metadata["feedback_source_copy"] = source.name
            tpstudio_metadata["feedback_format"] = "structured_v5"
            tpstudio_metadata["response_diagnostics_inserted"] = True
            tpstudio_metadata["response_cells_colored"] = True
            tpstudio_metadata["graph_diagnostics_inserted"] = True

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(updated, ensure_ascii=False, indent=1), encoding="utf-8")
    return output


def _color_response_cells(cells: list[dict], comparison: CopyComparison) -> list[dict]:
    diagnostics = diagnose_responses_from_notebook(comparison.copy_path)
    diagnostics_by_cell = {
        diagnosis.response.cell_number: diagnosis
        for diagnosis in diagnostics
    }

    colored_cells: list[dict] = []

    for index, cell in enumerate(cells, start=1):
        diagnosis = diagnostics_by_cell.get(index)
        if diagnosis and isinstance(cell, dict) and cell.get("cell_type") == "markdown":
            colored_cells.append(_colored_response_cell(cell, diagnosis))
        else:
            colored_cells.append(cell)

    return colored_cells


def _colored_response_cell(cell: dict, diagnosis: ResponseDiagnosis) -> dict:
    colored = copy.deepcopy(cell)
    display_level = _display_response_level(diagnosis)
    style = _response_level_style(display_level)
    label = _response_level_label(display_level)
    source = _cell_text(cell)
    escaped = _escape_html(source).replace("\n", "<br>\n")

    html = (
        f"<div style=\"{style}\">\n"
        f"<div style=\"font-weight: 700; margin-bottom: 0.35em;\">"
        f"TPStudio — réponse {label}</div>\n"
        f"{escaped}\n"
        "</div>\n"
    )

    colored["source"] = [html]

    metadata = colored.setdefault("metadata", {})
    if isinstance(metadata, dict):
        tpstudio = metadata.setdefault("tpstudio", {})
        if isinstance(tpstudio, dict):
            tpstudio["response_level"] = display_level
            tpstudio["response_colored"] = True

    return colored


def _response_level_style(level: str) -> str:
    base = (
        "padding: 0.85em 1em; "
        "border-radius: 8px; "
        "margin: 0.35em 0; "
        "border-left: 5px solid {border}; "
        "background-color: {background};"
    )

    if level == "solide":
        return base.format(background="#e8f5e9", border="#2e7d32")
    if level == "acceptable":
        return base.format(background="#fff3e0", border="#ef6c00")
    return base.format(background="#ffebee", border="#c62828")


def _response_level_label(level: str) -> str:
    if level == "solide":
        return "solide"
    if level == "acceptable":
        return "acceptable"
    if level == "fragile":
        return "fragile"
    return "à compléter"


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _cells_with_feedback(cells: list[dict], comparison: CopyComparison) -> list[dict]:
    local_comments = local_feedback_by_cell(comparison)

    new_cells: list[dict] = [_feedback_markdown_cell(comparison)]

    for index, cell in enumerate(cells, start=1):
        new_cells.append(cell)

        comments = local_comments.get(index, [])
        if comments:
            new_cells.append(_local_feedback_markdown_cell(index, comments))

    return new_cells


def _feedback_markdown_cell(comparison: CopyComparison) -> dict:
    source = structured_feedback_markdown(comparison)

    return {
        "cell_type": "markdown",
        "metadata": {"tpstudio": {"cell_role": "student_feedback", "format": "structured_v5"}},
        "source": source.splitlines(keepends=True),
    }


def _local_feedback_markdown_cell(cell_number: int, comments: list[str]) -> dict:
    bullet_lines = "\n".join(f"> - {comment}" for comment in comments)

    source = (
        "> 💬 **TPStudio — commentaire local**\n"
        ">\n"
        f"> Cellule concernée dans la copie originale : **{cell_number}**.\n"
        ">\n"
        f"{bullet_lines}\n"
    )

    return {
        "cell_type": "markdown",
        "metadata": {
            "tpstudio": {
                "cell_role": "local_feedback",
                "target_cell_number": cell_number,
                "position": "after_target_cell",
                "format": "structured_v4",
            }
        },
        "source": source.splitlines(keepends=True),
    }


def structured_feedback_markdown(comparison: CopyComparison) -> str:
    urgent_items = _urgent_feedback_items(comparison)
    check_items = _check_feedback_items(comparison)
    response_diagnostics = diagnose_responses_from_notebook(comparison.copy_path)
    graph_comparisons = compare_graphs(comparison.model_path, comparison.copy_path)
    response_items = _response_feedback_items(response_diagnostics)
    graph_items = _graph_feedback_items(graph_comparisons)
    local_comments = local_feedback_by_cell(comparison)
    summary_items = _summary_items(
        comparison,
        urgent_items,
        check_items,
        local_comments,
        response_diagnostics,
        graph_comparisons,
    )
    priority_items = _priority_items(
        urgent_items,
        check_items,
        response_diagnostics,
        graph_comparisons,
    )
    advice_items = _advice_items(
        comparison,
        urgent_items,
        check_items,
        response_diagnostics,
        graph_comparisons,
    )

    sections = [
        "## Retour TPStudio",
        "",
        "Ce retour automatique signale les points techniques, rédactionnels et graphiques à vérifier avant une correction détaillée.",
        "",
        "### Synthèse rapide",
        *_bullet_lines(summary_items),
        "",
        "### Priorités avant nouveau rendu",
        *_bullet_lines(priority_items, empty="Aucune priorité évidente détectée."),
        "",
        "### Diagnostic des réponses",
        *_bullet_lines(response_items, empty="Aucune zone `Réponse :` détectée."),
        "",
        "### Diagnostic des graphes",
        *_bullet_lines(graph_items, empty="Aucun graphe matplotlib détecté."),
        "",
        "### Conseils ciblés",
        *_bullet_lines(advice_items),
        "",
    ]

    return "\n".join(sections)


def local_feedback_by_cell(comparison: CopyComparison) -> dict[int, list[str]]:
    comments: dict[int, list[str]] = {}
    sources = _cell_sources_by_number(comparison.copy_path)

    for issue in comparison.copy.issues:
        source = sources.get(issue.cell_number, issue.preview)

        if _should_skip_local_comment(issue.kind, source):
            continue

        comment = _local_comment_for_issue(issue.kind)
        if not comment:
            continue

        comments.setdefault(issue.cell_number, []).append(comment)

    for diagnosis in diagnose_responses_from_notebook(comparison.copy_path):
        response_comment = _local_comment_for_response_diagnosis(diagnosis)
        if not response_comment:
            continue

        comments.setdefault(diagnosis.response.cell_number, []).append(response_comment)

    for graph_comparison in compare_graphs(comparison.model_path, comparison.copy_path):
        graph_comment = _local_comment_for_graph_comparison(graph_comparison)
        if not graph_comment:
            continue

        copy_graph = graph_comparison.copy_graph
        if copy_graph is None:
            continue

        comments.setdefault(copy_graph.cell_number, []).append(graph_comment)

    return {
        cell_number: _deduplicate(cell_comments)
        for cell_number, cell_comments in comments.items()
    }


def _local_comment_for_response_diagnosis(diagnosis: ResponseDiagnosis) -> str:
    display_level = _display_response_level(diagnosis)

    if display_level not in {"fragile", "à compléter"}:
        return ""

    if display_level == "fragile":
        main = "Cette réponse semble fragile"
    else:
        main = "Cette réponse est à compléter"

    signals = "; ".join(diagnosis.signals)
    if signals:
        return f"{main} : {signals}."

    return main + "."


def _local_comment_for_graph_comparison(comparison: GraphComparison) -> str:
    if not _graph_needs_attention(comparison):
        return ""

    findings = _important_graph_findings(comparison)
    if not findings:
        return ""

    return "Ce graphe est à vérifier : " + "; ".join(findings) + "."


def _response_feedback_items(diagnostics: list[ResponseDiagnosis]) -> list[str]:
    if not diagnostics:
        return []

    counts = _display_response_level_counts(diagnostics)
    items = [
        f"Réponses analysées : **{len(diagnostics)}** — solides : **{counts.get('solide', 0)}**, acceptables : **{counts.get('acceptable', 0)}**, fragiles : **{counts.get('fragile', 0)}**, à compléter : **{counts.get('à compléter', 0)}**.",
    ]

    for diagnosis in diagnostics:
        display_level = _display_response_level(diagnosis)
        label = _response_cell_label(diagnosis)
        signal_text = _readable_response_signal_text(diagnosis)
        items.append(f"{_level_icon(display_level)} {label} : **{display_level}** — {signal_text}.")

    return items


def _display_response_level(diagnosis: ResponseDiagnosis) -> str:
    if diagnosis.response.is_empty:
        return "à compléter"

    # Une réponse courte peut contenir un mot vague comme "proche" tout en étant
    # pédagogiquement correcte si elle donne une valeur, une comparaison et le
    # vocabulaire physique attendu.
    if (
        diagnosis.has_numeric_value
        and diagnosis.has_comparison
        and diagnosis.has_physical_vocabulary
    ):
        return "solide"

    return diagnosis.level


def _display_response_level_counts(diagnostics: list[ResponseDiagnosis]) -> dict[str, int]:
    counts: dict[str, int] = {}

    for diagnosis in diagnostics:
        level = _display_response_level(diagnosis)
        counts[level] = counts.get(level, 0) + 1

    return counts


def _readable_response_signal_text(diagnosis: ResponseDiagnosis) -> str:
    if _display_response_level(diagnosis) == "solide":
        positive_signals: list[str] = []

        if diagnosis.has_numeric_value:
            positive_signals.append("valeur numérique détectée")
        if diagnosis.has_comparison:
            positive_signals.append("comparaison explicite détectée")
        if diagnosis.has_physical_vocabulary:
            positive_signals.append("vocabulaire physique présent")

        if positive_signals:
            return "; ".join(positive_signals)

        return "réponse structurée sur le plan textuel"

    return "; ".join(diagnosis.signals)


def _level_icon(level: str) -> str:
    if level == "solide":
        return "✅"
    if level == "acceptable":
        return "🟡"
    if level == "fragile":
        return "⚠️"
    return "❌"


def _response_level_counts(diagnostics: list[ResponseDiagnosis]) -> dict[str, int]:
    counts: dict[str, int] = {}

    for diagnosis in diagnostics:
        counts[diagnosis.level] = counts.get(diagnosis.level, 0) + 1

    return counts


def _response_cell_label(diagnosis: ResponseDiagnosis) -> str:
    response = diagnosis.response
    if response.context:
        return f"Cellule {response.cell_number} — partie « {response.context} »"
    return f"Cellule {response.cell_number}"


def _graph_feedback_items(comparisons: list[GraphComparison]) -> list[str]:
    if not comparisons:
        return []

    graph_count = len(comparisons)
    graph_to_check = sum(1 for comparison in comparisons if _graph_needs_attention(comparison))

    items = [
        f"Graphes analysés : **{graph_count}** — graphes à vérifier : **{graph_to_check}**.",
    ]

    for comparison in comparisons:
        icon = "⚠️" if _graph_needs_attention(comparison) else "✅"
        label = _graph_label(comparison)
        findings = "; ".join(_important_graph_findings(comparison))
        items.append(f"{icon} {label} : **{comparison.level}** — {findings}.")

    return items


def _graph_needs_attention(comparison: GraphComparison) -> bool:
    return comparison.level != "cohérent"


def _graph_label(comparison: GraphComparison) -> str:
    graph = comparison.copy_graph or comparison.model_graph

    if graph is None:
        return f"Graphe {comparison.index}"

    label = f"Graphe {comparison.index} — cellule {graph.cell_number}"
    if graph.context:
        label += f" — partie « {graph.context} »"
    return label


def _important_graph_findings(comparison: GraphComparison) -> list[str]:
    if not comparison.findings:
        return ["aucun indice disponible"]

    return comparison.findings


def _priority_items(
    urgent_items: list[str],
    check_items: list[str],
    response_diagnostics: list[ResponseDiagnosis],
    graph_comparisons: list[GraphComparison],
) -> list[str]:
    items: list[str] = []

    items.extend(urgent_items)

    weak_responses = [
        diagnosis
        for diagnosis in response_diagnostics
        if _display_response_level(diagnosis) in {"fragile", "à compléter"}
    ]

    for diagnosis in weak_responses:
        label = _response_cell_label(diagnosis)
        signal_text = "; ".join(diagnosis.signals)
        items.append(f"{label} : réponse **{_display_response_level(diagnosis)}** — {signal_text}.")

    for graph_comparison in graph_comparisons:
        if not _graph_needs_attention(graph_comparison):
            continue

        label = _graph_label(graph_comparison)
        findings = "; ".join(_important_graph_findings(graph_comparison))
        items.append(f"{label} : graphe **à vérifier** — {findings}.")

    # Keep the priority section readable, but do not hide the exact diagnostics.
    for check_item in check_items:
        items.append(f"Point technique à vérifier : {check_item}")

    return _deduplicate(items)


def _should_skip_local_comment(kind: str, source: str) -> bool:
    if kind in {"not_executed", "missing_output"} and _is_setup_only_code(source):
        return True

    return False


def _is_setup_only_code(source: str) -> bool:
    meaningful_lines = _meaningful_code_lines(source)
    if not meaningful_lines:
        return True

    in_rcparams_block = False

    for line in meaningful_lines:
        stripped = line.strip()

        if "rcParams.update" in stripped:
            in_rcparams_block = True
            continue

        if in_rcparams_block:
            if stripped in {"}", "})", ")"} or stripped.endswith("})"):
                in_rcparams_block = False
                continue
            if _looks_like_dict_item(stripped):
                continue

        if _is_setup_line(stripped):
            continue

        return False

    return True


def _meaningful_code_lines(source: str) -> list[str]:
    lines: list[str] = []

    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        lines.append(stripped)

    return lines


def _is_setup_line(line: str) -> bool:
    setup_prefixes = (
        "import ",
        "from ",
        "%matplotlib",
        "plt.rcParams",
        "matplotlib.rcParams",
        "rcParams",
        "np.set_printoptions",
        "pd.set_option",
        "warnings.filterwarnings",
    )

    return line.startswith(setup_prefixes)


def _looks_like_dict_item(line: str) -> bool:
    if line in {"{", "}", "},", "})", ")"}:
        return True

    return re.match(r"^[\"'].*[\"']\s*:\s*.+,?$", line) is not None


def _local_comment_for_issue(kind: str) -> str:
    if kind == "code_to_complete_not_executed":
        return "Cette cellule contient encore du code à compléter (`?`) et n'a pas été exécutée."
    if kind == "code_to_complete":
        return "Cette cellule contient encore du code à compléter (`?`) : complétez puis relancez."
    if kind == "execution_error":
        return "Cette cellule produit une erreur d'exécution : corrigez l'erreur puis relancez le notebook."
    if kind == "not_executed":
        return "Cette cellule de code n'a pas été exécutée."
    if kind == "missing_output":
        return "Cette cellule a été exécutée sans sortie visible : vérifiez que c'est bien attendu."
    if kind == "empty_response":
        return "Cette réponse est vide ou à compléter."
    if kind == "short_response":
        return "Cette réponse est très courte : vérifiez qu'elle est suffisamment justifiée."

    return ""


def _cell_sources_by_number(notebook_path: str | Path) -> dict[int, str]:
    try:
        data = json.loads(Path(notebook_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    cells = data.get("cells", [])
    if not isinstance(cells, list):
        return {}

    return {
        index: _cell_text(cell)
        for index, cell in enumerate(cells, start=1)
        if isinstance(cell, dict)
    }


def _cell_text(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source)


def _global_readiness_level(
    comparison: CopyComparison,
    response_diagnostics: list[ResponseDiagnosis],
    graph_comparisons: list[GraphComparison],
) -> str:
    technical_level = comparison.readiness_level

    if technical_level in {"à reprendre", "non corrigeable"}:
        return technical_level

    weak_responses = [
        diagnosis
        for diagnosis in response_diagnostics
        if _display_response_level(diagnosis) in {"fragile", "à compléter"}
    ]
    graph_issues = [
        graph_comparison
        for graph_comparison in graph_comparisons
        if _graph_needs_attention(graph_comparison)
    ]

    if graph_issues:
        return "à vérifier"

    if weak_responses and technical_level == "exploitable":
        return "à vérifier"

    return technical_level


def _global_readiness_reason(
    comparison: CopyComparison,
    response_diagnostics: list[ResponseDiagnosis],
    graph_comparisons: list[GraphComparison],
) -> str:
    technical_level = comparison.readiness_level

    if technical_level in {"à reprendre", "non corrigeable"}:
        return "blocages techniques prioritaires"

    graph_issues = [
        graph_comparison
        for graph_comparison in graph_comparisons
        if _graph_needs_attention(graph_comparison)
    ]
    if graph_issues:
        return "au moins un graphe important est à vérifier"

    weak_responses = [
        diagnosis
        for diagnosis in response_diagnostics
        if _display_response_level(diagnosis) in {"fragile", "à compléter"}
    ]
    if weak_responses and technical_level == "exploitable":
        return "certaines réponses doivent être renforcées"

    return "aucun blocage majeur détecté"


def _summary_items(
    comparison: CopyComparison,
    urgent_items: list[str],
    check_items: list[str],
    local_comments: dict[int, list[str]],
    response_diagnostics: list[ResponseDiagnosis],
    graph_comparisons: list[GraphComparison],
) -> list[str]:
    copy_diagnostic = comparison.copy
    response_counts = _display_response_level_counts(response_diagnostics)
    weak_responses = response_counts.get("fragile", 0) + response_counts.get("à compléter", 0)
    graphs_to_check = sum(1 for graph_comparison in graph_comparisons if _graph_needs_attention(graph_comparison))

    global_readiness = _global_readiness_level(
        comparison,
        response_diagnostics,
        graph_comparisons,
    )
    global_reason = _global_readiness_reason(
        comparison,
        response_diagnostics,
        graph_comparisons,
    )
    pedagogical_findings = _pedagogical_findings_summary(
        weak_responses,
        graphs_to_check,
    )

    items = [
        f"Corrigeabilité globale : **{global_readiness}**.",
        f"Raison principale : **{global_reason}**.",
        f"Corrigeabilité technique : **{comparison.readiness_level}**.",
        f"Code à reprendre : **{len(urgent_items)}** point(s).",
    ]

    if pedagogical_findings:
        items.append(
            "Points pédagogiques déjà détectés : "
            + "; ".join(pedagogical_findings)
            + "."
        )

    items.extend(
        [
            f"Réponses fragiles ou à compléter : **{weak_responses}**.",
            f"Graphes à vérifier : **{graphs_to_check}**.",
            f"Commentaires locaux insérés : **{len(local_comments)}**.",
        ]
    )

    if getattr(copy_diagnostic, "code_cells_to_complete", 0):
        items.append(f"Cellules contenant encore du code à compléter : **{copy_diagnostic.code_cells_to_complete}**.")

    if copy_diagnostic.code_cells_not_executed:
        items.append(f"Cellules de code non exécutées : **{copy_diagnostic.code_cells_not_executed}**.")

    return items


def _pedagogical_findings_summary(
    weak_responses: int,
    graphs_to_check: int,
) -> list[str]:
    findings: list[str] = []

    if weak_responses == 1:
        findings.append("1 réponse fragile ou à compléter")
    elif weak_responses > 1:
        findings.append(f"{weak_responses} réponses fragiles ou à compléter")

    if graphs_to_check == 1:
        findings.append("1 graphe à vérifier")
    elif graphs_to_check > 1:
        findings.append(f"{graphs_to_check} graphes à vérifier")

    return findings


def _urgent_feedback_items(comparison: CopyComparison) -> list[str]:
    items: list[str] = []

    for issue in comparison.copy.issues:
        label = _student_cell_label(comparison, issue.cell_number)

        if issue.kind == "code_to_complete_not_executed":
            items.append(f"{label} : complétez cette cellule puis exécutez-la.")
        elif issue.kind == "code_to_complete":
            items.append(f"{label} : le code contient encore un `?` ; complétez puis relancez.")
        elif issue.kind == "execution_error":
            items.append(f"{label} : erreur d'exécution à corriger.")
        elif issue.kind == "empty_response":
            items.append(f"{label} : réponse à compléter.")

    if comparison.model.response_cells and comparison.copy.response_cells == 0:
        items.append("La copie ne reprend pas les zones `Réponse :` du modèle distribué.")
    elif comparison.missing_response_cells:
        items.append("Certaines zones `Réponse :` attendues ne sont pas identifiables.")

    if comparison.missing_result_cells:
        items.append("Certains résultats attendus ne sont pas identifiables dans la copie.")

    return _deduplicate(items)


def _check_feedback_items(comparison: CopyComparison) -> list[str]:
    items: list[str] = []

    sources = _cell_sources_by_number(comparison.copy_path)

    for issue in comparison.copy.issues:
        source = sources.get(issue.cell_number, issue.preview)
        if _should_skip_local_comment(issue.kind, source):
            continue

        label = _student_cell_label(comparison, issue.cell_number)

        if issue.kind == "not_executed":
            items.append(f"{label} : cellule de code à exécuter.")
        elif issue.kind == "missing_output":
            items.append(f"{label} : cellule exécutée sans sortie visible ; vérifiez que c'est attendu.")
        elif issue.kind == "short_response":
            items.append(f"{label} : réponse très courte à relire.")

    if comparison.missing_interpretation_cells:
        items.append("Certaines interprétations attendues ne sont pas identifiables.")

    if comparison.missing_checklist_cells:
        items.append("La checklist ou grille finale attendue n'est pas identifiable.")

    return _deduplicate(items)


def _advice_items(
    comparison: CopyComparison,
    urgent_items: list[str],
    check_items: list[str],
    response_diagnostics: list[ResponseDiagnosis],
    graph_comparisons: list[GraphComparison],
) -> list[str]:
    items = [
        "Relancez le notebook depuis le début avant de le rendre.",
        "Vérifiez qu'il ne reste plus de cellule avec `?` dans le code.",
    ]

    weak_responses = [
        diagnosis
        for diagnosis in response_diagnostics
        if _display_response_level(diagnosis) in {"fragile", "à compléter"}
    ]
    graph_issues = [
        graph_comparison
        for graph_comparison in graph_comparisons
        if _graph_needs_attention(graph_comparison)
    ]

    if weak_responses:
        items.append("Reprenez les réponses signalées comme fragiles ou à compléter.")

    if graph_issues:
        items.append("Vérifiez les graphes signalés comme à vérifier, en particulier les axes, les labels et les variables de régression.")

    global_readiness = _global_readiness_level(comparison, response_diagnostics, graph_comparisons)

    if urgent_items:
        items.append("Après correction, relisez les priorités du bloc `Retour TPStudio`.")
    elif global_readiness == "à vérifier":
        items.append("Le notebook est techniquement exploitable, mais il doit être vérifié avant correction détaillée.")
    elif check_items or weak_responses or graph_issues:
        items.append("Le notebook semble exploitable, mais vérifiez les points listés.")
    else:
        items.append("Le notebook semble exploitable pour une correction détaillée.")

    return items


def _bullet_lines(items: list[str], *, empty: str | None = None) -> list[str]:
    if not items:
        if empty is None:
            return []
        return [f"- {empty}"]

    return [f"- {item}" for item in items]


def _student_cell_label(comparison: CopyComparison, cell_number: int) -> str:
    context = comparison.context_for_cell(cell_number)
    if context:
        return f"Cellule {cell_number} — {context}"
    return f"Cellule {cell_number}"


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)

    return result


def _next_available_feedback_path(copy_path: Path) -> Path:
    base = copy_path.with_name(copy_path.stem + "-retour-tpstudio.ipynb")
    if not base.exists():
        return base

    counter = 2
    while True:
        candidate = copy_path.with_name(copy_path.stem + f"-retour-tpstudio-{counter}.ipynb")
        if not candidate.exists():
            return candidate
        counter += 1

def create_feedback_notebook(
    model_path,
    copy_path,
    output_path=None,
):
    if output_path is None:
        result = _tpstudio_original_create_feedback_notebook_a61a(
            model_path,
            copy_path,
        )
        corrected_path = result
    else:
        result = _tpstudio_original_create_feedback_notebook_a61a(
            model_path,
            copy_path,
            output_path,
        )
        corrected_path = result if result is not None else output_path

    add_pedagogical_section_feedback_to_notebook(
        copy_path,
        corrected_path,
    )
    add_code_semantic_feedback_to_notebook(
        model_path,
        copy_path,
        corrected_path,
    )
    return result

