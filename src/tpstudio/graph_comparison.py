from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path


@dataclass(frozen=True)
class GraphSignature:
    cell_number: int
    context: str
    function_name: str
    x_expression: str
    y_expression: str
    xlabel: str
    ylabel: str
    title: str
    has_legend: bool
    polyfit_x: str
    polyfit_y: str


@dataclass(frozen=True)
class GraphComparison:
    index: int
    model_graph: GraphSignature | None
    copy_graph: GraphSignature | None
    level: str
    findings: list[str]


def extract_graph_signatures(notebook_path: str | Path) -> list[GraphSignature]:
    path = Path(notebook_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    cells = data.get("cells", [])
    if not isinstance(cells, list):
        return []

    graphs: list[GraphSignature] = []
    current_context = ""

    for index, cell in enumerate(cells, start=1):
        if not isinstance(cell, dict):
            continue

        source = _cell_text(cell)

        if cell.get("cell_type") == "markdown":
            heading = _extract_heading(source)
            if heading:
                current_context = heading
            continue

        if cell.get("cell_type") != "code":
            continue

        signature = _graph_signature_from_code_cell(index, current_context, source)
        if signature is not None:
            graphs.append(signature)

    return graphs


def compare_graphs(model_path: str | Path, copy_path: str | Path) -> list[GraphComparison]:
    model_graphs = extract_graph_signatures(model_path)
    copy_graphs = extract_graph_signatures(copy_path)
    total = max(len(model_graphs), len(copy_graphs))

    comparisons: list[GraphComparison] = []

    for index in range(total):
        model_graph = model_graphs[index] if index < len(model_graphs) else None
        copy_graph = copy_graphs[index] if index < len(copy_graphs) else None
        findings = _compare_graph_pair(model_graph, copy_graph)
        level = _graph_level(findings)

        comparisons.append(
            GraphComparison(
                index=index + 1,
                model_graph=model_graph,
                copy_graph=copy_graph,
                level=level,
                findings=findings,
            )
        )

    return comparisons


def format_graph_comparison_report(model_path: str | Path, copy_path: str | Path) -> str:
    model_graphs = extract_graph_signatures(model_path)
    copy_graphs = extract_graph_signatures(copy_path)
    comparisons = compare_graphs(model_path, copy_path)

    lines = [
        "TPStudio - Comparaison des graphes",
        "────────────────────────────────",
        "",
        f"📘 Modèle : {Path(model_path).name}",
        f"📓 Copie : {Path(copy_path).name}",
        "",
        f"Graphes détectés dans le modèle : {len(model_graphs)}",
        f"Graphes détectés dans la copie : {len(copy_graphs)}",
    ]

    if not comparisons:
        lines.append("")
        lines.append("Aucun graphe matplotlib détecté.")
        return "\n".join(lines)

    for comparison in comparisons:
        model_graph = comparison.model_graph
        copy_graph = comparison.copy_graph

        lines.append("")
        lines.append(f"Graphe {comparison.index}")
        lines.append(f"    niveau : {comparison.level}")

        if model_graph is not None:
            lines.append(
                "    modèle : "
                + _graph_location(model_graph)
                + f" — x={model_graph.x_expression}, y={model_graph.y_expression}"
            )

        if copy_graph is not None:
            lines.append(
                "    copie : "
                + _graph_location(copy_graph)
                + f" — x={copy_graph.x_expression}, y={copy_graph.y_expression}"
            )

        lines.append("    indices :")
        for finding in comparison.findings:
            lines.append(f"        • {finding}")

    return "\n".join(lines)


def _graph_signature_from_code_cell(
    cell_number: int,
    context: str,
    source: str,
) -> GraphSignature | None:
    plot_call = _first_plot_call(source)
    if plot_call is None:
        return None

    function_name, args = plot_call

    x_expression = args[0] if len(args) >= 1 else ""
    y_expression = args[1] if len(args) >= 2 else ""

    polyfit_args = _first_call_args(source, "np.polyfit")
    polyfit_x = polyfit_args[0] if len(polyfit_args) >= 1 else ""
    polyfit_y = polyfit_args[1] if len(polyfit_args) >= 2 else ""

    return GraphSignature(
        cell_number=cell_number,
        context=context,
        function_name=function_name,
        x_expression=x_expression,
        y_expression=y_expression,
        xlabel=_extract_matplotlib_string_arg(source, "xlabel"),
        ylabel=_extract_matplotlib_string_arg(source, "ylabel"),
        title=_extract_matplotlib_string_arg(source, "title"),
        has_legend="plt.legend" in source,
        polyfit_x=polyfit_x,
        polyfit_y=polyfit_y,
    )


def _compare_graph_pair(
    model_graph: GraphSignature | None,
    copy_graph: GraphSignature | None,
) -> list[str]:
    if model_graph is None and copy_graph is None:
        return ["aucun graphe à comparer"]

    if model_graph is None:
        return ["graphe présent dans la copie, mais absent du modèle"]

    if copy_graph is None:
        return ["graphe attendu dans le modèle, mais absent de la copie"]

    findings: list[str] = []

    model_x = _normalize_expression(model_graph.x_expression)
    model_y = _normalize_expression(model_graph.y_expression)
    copy_x = _normalize_expression(copy_graph.x_expression)
    copy_y = _normalize_expression(copy_graph.y_expression)

    if model_x == copy_x and model_y == copy_y:
        findings.append("expressions tracées cohérentes avec le modèle")
    elif model_x == copy_y and model_y == copy_x:
        findings.append(
            "axes probablement inversés : les expressions en abscisse et en ordonnée sont échangées par rapport au modèle"
        )
    else:
        if model_x != copy_x:
            findings.append(f"expression en abscisse différente : attendu `{model_graph.x_expression}`, obtenu `{copy_graph.x_expression}`")
        if model_y != copy_y:
            findings.append(f"expression en ordonnée différente : attendu `{model_graph.y_expression}`, obtenu `{copy_graph.y_expression}`")

    model_xlabel = _normalize_label(model_graph.xlabel)
    model_ylabel = _normalize_label(model_graph.ylabel)
    copy_xlabel = _normalize_label(copy_graph.xlabel)
    copy_ylabel = _normalize_label(copy_graph.ylabel)

    if model_xlabel and copy_xlabel and model_xlabel != copy_xlabel:
        findings.append(f"label de l'axe horizontal différent : attendu `{model_graph.xlabel}`, obtenu `{copy_graph.xlabel}`")

    if model_ylabel and copy_ylabel and model_ylabel != copy_ylabel:
        findings.append(f"label de l'axe vertical différent : attendu `{model_graph.ylabel}`, obtenu `{copy_graph.ylabel}`")

    if model_xlabel and model_ylabel and copy_xlabel == model_ylabel and copy_ylabel == model_xlabel:
        findings.append("labels d'axes probablement inversés")

    if model_graph.has_legend and not copy_graph.has_legend:
        findings.append("légende attendue mais absente dans la copie")

    if model_graph.polyfit_x and model_graph.polyfit_y:
        model_polyfit = (
            _normalize_expression(model_graph.polyfit_x),
            _normalize_expression(model_graph.polyfit_y),
        )
        copy_polyfit = (
            _normalize_expression(copy_graph.polyfit_x),
            _normalize_expression(copy_graph.polyfit_y),
        )

        if not copy_graph.polyfit_x or not copy_graph.polyfit_y:
            findings.append("régression linéaire attendue mais non détectée dans la copie")
        elif model_polyfit == copy_polyfit:
            findings.append("régression linéaire cohérente avec le modèle")
        elif model_polyfit == (copy_polyfit[1], copy_polyfit[0]):
            findings.append("régression linéaire probablement effectuée avec les axes inversés")
        else:
            findings.append("régression linéaire détectée, mais variables différentes du modèle")

    if not findings:
        findings.append("aucune anomalie évidente détectée")

    return _deduplicate(findings)


def _graph_level(findings: list[str]) -> str:
    serious_markers = [
        "absent",
        "axes probablement inversés",
        "différente",
        "différent",
        "inversés",
        "variables différentes",
    ]

    if any(any(marker in finding for marker in serious_markers) for finding in findings):
        return "à vérifier"

    return "cohérent"


def _first_plot_call(source: str) -> tuple[str, list[str]] | None:
    for function_name in ["plt.errorbar", "plt.scatter", "plt.plot"]:
        args = _first_call_args(source, function_name)
        if args:
            return function_name, args

    return None


def _first_call_args(source: str, function_name: str) -> list[str]:
    start = source.find(function_name + "(")
    if start == -1:
        return []

    open_paren = source.find("(", start)
    if open_paren == -1:
        return []

    close_paren = _matching_closing_parenthesis(source, open_paren)
    if close_paren == -1:
        return []

    inside = source[open_paren + 1 : close_paren]
    return _split_top_level_args(inside)


def _matching_closing_parenthesis(text: str, open_index: int) -> int:
    depth = 0
    quote: str | None = None
    escape = False

    for index in range(open_index, len(text)):
        char = text[index]

        if quote is not None:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue

        if char in {"'", '"'}:
            quote = char
            continue

        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index

    return -1


def _split_top_level_args(text: str) -> list[str]:
    args: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escape = False

    for index, char in enumerate(text):
        if quote is not None:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue

        if char in {"'", '"'}:
            quote = char
            continue

        if char in "([{":
            depth += 1
            continue

        if char in ")]}":
            depth -= 1
            continue

        if char == "," and depth == 0:
            args.append(text[start:index].strip())
            start = index + 1

    last = text[start:].strip()
    if last:
        args.append(last)

    return args


def _extract_matplotlib_string_arg(source: str, method_name: str) -> str:
    pattern = rf"plt\.{method_name}\((.*?)\)"
    match = re.search(pattern, source, flags=re.DOTALL)
    if not match:
        return ""

    args = _split_top_level_args(match.group(1))
    if not args:
        return ""

    return _strip_string_quotes(args[0])


def _strip_string_quotes(text: str) -> str:
    stripped = text.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def _normalize_expression(expression: str) -> str:
    return re.sub(r"\s+", "", expression).lower()


def _normalize_label(label: str) -> str:
    normalized = label.lower()
    normalized = normalized.replace("$", "")
    normalized = normalized.replace("\\", "")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def _graph_location(graph: GraphSignature) -> str:
    location = f"cellule {graph.cell_number}"
    if graph.context:
        location += f" — partie « {graph.context} »"
    return location


def _cell_text(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source)


def _extract_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            return _clean_heading(match.group(1))

    return ""


def _clean_heading(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^[#\s]+", "", cleaned)
    cleaned = re.sub(r"\s+#*$", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("__", "")
    return cleaned.strip()


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)

    return result
