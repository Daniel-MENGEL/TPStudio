from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from tpstudio.copy_comparison import (
    CopyComparison,
    compare_copy_to_model,
)
from tpstudio.graph_comparison import compare_graphs
from tpstudio.response_diagnostics import diagnose_responses_from_notebook


@dataclass(frozen=True)
class CopySummary:
    file: str
    path: str
    global_readiness: str
    main_reason: str
    technical_readiness: str
    code_to_rework: int
    responses_solid: int
    responses_acceptable: int
    responses_fragile: int
    responses_to_complete: int
    graphs_to_check: int
    code_cells_to_complete: int
    code_cells_not_executed: int


CSV_COLUMNS = [
    "fichier",
    "chemin",
    "corrigeabilite_globale",
    "raison_principale",
    "corrigeabilite_technique",
    "code_a_reprendre",
    "reponses_solides",
    "reponses_acceptables",
    "reponses_fragiles",
    "reponses_a_completer",
    "graphes_a_verifier",
    "cellules_code_a_completer",
    "cellules_code_non_executees",
]


def summarize_copy(model_path: str | Path, copy_path: str | Path) -> CopySummary:
    model = Path(model_path)
    copy = Path(copy_path)

    comparison = compare_copy_to_model(model, copy)
    response_diagnostics = diagnose_responses_from_notebook(copy)
    graph_comparisons = compare_graphs(model, copy)

    response_counts = _response_level_counts_for_summary(response_diagnostics)
    graphs_to_check = sum(
        1 for graph_comparison in graph_comparisons
        if graph_comparison.level != "cohérent"
    )

    return CopySummary(
        file=copy.name,
        path=str(copy),
        global_readiness=_global_readiness_level(
            comparison,
            response_counts,
            graphs_to_check,
        ),
        main_reason=_global_readiness_reason(
            comparison,
            response_counts,
            graphs_to_check,
        ),
        technical_readiness=comparison.readiness_level,
        code_to_rework=_code_to_rework_count(comparison),
        responses_solid=response_counts.get("solide", 0),
        responses_acceptable=response_counts.get("acceptable", 0),
        responses_fragile=response_counts.get("fragile", 0),
        responses_to_complete=response_counts.get("à compléter", 0),
        graphs_to_check=graphs_to_check,
        code_cells_to_complete=getattr(comparison.copy, "code_cells_to_complete", 0),
        code_cells_not_executed=comparison.copy.code_cells_not_executed,
    )


def summarize_copies(
    model_path: str | Path,
    copies_dir: str | Path,
    *,
    pattern: str = "*.ipynb",
) -> list[CopySummary]:
    model = Path(model_path).resolve()
    directory = Path(copies_dir)

    summaries: list[CopySummary] = []

    for copy_path in sorted(directory.glob(pattern)):
        if not copy_path.is_file():
            continue

        if _should_ignore_notebook(copy_path, model):
            continue

        summaries.append(summarize_copy(model, copy_path))

    return summaries


def export_copies_summary_csv(
    model_path: str | Path,
    copies_dir: str | Path,
    output_path: str | Path,
    *,
    pattern: str = "*.ipynb",
) -> Path:
    output = Path(output_path)
    summaries = summarize_copies(model_path, copies_dir, pattern=pattern)

    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for summary in summaries:
            writer.writerow(summary_to_csv_row(summary))

    return output


def summary_to_csv_row(summary: CopySummary) -> dict[str, str | int]:
    return {
        "fichier": summary.file,
        "chemin": summary.path,
        "corrigeabilite_globale": summary.global_readiness,
        "raison_principale": summary.main_reason,
        "corrigeabilite_technique": summary.technical_readiness,
        "code_a_reprendre": summary.code_to_rework,
        "reponses_solides": summary.responses_solid,
        "reponses_acceptables": summary.responses_acceptable,
        "reponses_fragiles": summary.responses_fragile,
        "reponses_a_completer": summary.responses_to_complete,
        "graphes_a_verifier": summary.graphs_to_check,
        "cellules_code_a_completer": summary.code_cells_to_complete,
        "cellules_code_non_executees": summary.code_cells_not_executed,
    }


def _should_ignore_notebook(copy_path: Path, model_path: Path) -> bool:
    try:
        if copy_path.resolve() == model_path:
            return True
    except OSError:
        pass

    name = copy_path.name.lower()
    stem = copy_path.stem.lower()

    generated_markers = [
        "-retour-tpstudio",
        "-rapport-tpstudio",
        "-retour-a",
        "-retour_",
        "retour-tpstudio",
    ]

    if any(marker in stem for marker in generated_markers):
        return True

    if name.startswith("."):
        return True

    return False


def _response_level_counts_for_summary(diagnostics) -> dict[str, int]:
    counts: dict[str, int] = {}

    for diagnosis in diagnostics:
        level = _display_response_level_for_summary(diagnosis)
        counts[level] = counts.get(level, 0) + 1

    return counts


def _display_response_level_for_summary(diagnosis) -> str:
    if diagnosis.response.is_empty:
        return "à compléter"

    if (
        diagnosis.has_numeric_value
        and diagnosis.has_comparison
        and diagnosis.has_physical_vocabulary
    ):
        return "solide"

    return diagnosis.level


def _global_readiness_level(
    comparison: CopyComparison,
    response_counts: dict[str, int],
    graphs_to_check: int,
) -> str:
    technical_level = comparison.readiness_level

    if technical_level in {"à reprendre", "non corrigeable"}:
        return technical_level

    weak_responses = response_counts.get("fragile", 0) + response_counts.get("à compléter", 0)

    if graphs_to_check:
        return "à vérifier"

    if weak_responses and technical_level == "exploitable":
        return "à vérifier"

    return technical_level


def _global_readiness_reason(
    comparison: CopyComparison,
    response_counts: dict[str, int],
    graphs_to_check: int,
) -> str:
    technical_level = comparison.readiness_level

    if technical_level in {"à reprendre", "non corrigeable"}:
        return "blocages techniques prioritaires"

    if graphs_to_check:
        return "au moins un graphe important est à vérifier"

    weak_responses = response_counts.get("fragile", 0) + response_counts.get("à compléter", 0)
    if weak_responses and technical_level == "exploitable":
        return "certaines réponses doivent être renforcées"

    return "aucun blocage majeur détecté"


def _code_to_rework_count(comparison: CopyComparison) -> int:
    blocking_kinds = {
        "code_to_complete_not_executed",
        "code_to_complete",
        "execution_error",
        "empty_response",
    }

    return sum(1 for issue in comparison.copy.issues if issue.kind in blocking_kinds)
