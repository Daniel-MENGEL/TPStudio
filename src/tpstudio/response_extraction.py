from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path


@dataclass(frozen=True)
class NotebookResponse:
    cell_number: int
    context: str
    text: str
    word_count: int
    is_empty: bool


def extract_responses_from_notebook(notebook_path: str | Path) -> list[NotebookResponse]:
    """Extract student response zones from a notebook.

    A response zone is currently identified in Markdown cells containing a
    marker such as "Réponse :". The extracted text is the content that follows
    the marker in the same cell.
    """

    path = Path(notebook_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    cells = data.get("cells", [])
    if not isinstance(cells, list):
        return []

    responses: list[NotebookResponse] = []
    current_context = ""

    for index, cell in enumerate(cells, start=1):
        if not isinstance(cell, dict):
            continue

        cell_type = cell.get("cell_type", "")
        source = _cell_text(cell)

        if cell_type == "markdown":
            heading = _extract_heading(source)
            if heading:
                current_context = heading

            extracted = _extract_response_text(source)
            if extracted is not None:
                text = _clean_response_text(extracted)
                responses.append(
                    NotebookResponse(
                        cell_number=index,
                        context=current_context,
                        text=text,
                        word_count=_word_count(text),
                        is_empty=_is_empty_response(text),
                    )
                )

    return responses


def format_response_extraction_report(notebook_path: str | Path) -> str:
    responses = extract_responses_from_notebook(notebook_path)

    lines = [
        f"Réponses détectées : {len(responses)}",
    ]

    if not responses:
        lines.append("Aucune zone `Réponse :` détectée.")
        return "\n".join(lines)

    for number, response in enumerate(responses, start=1):
        lines.append("")
        title = f"Réponse {number} — cellule {response.cell_number}"
        if response.context:
            title += f" — partie « {response.context} »"
        lines.append(title)

        if response.is_empty:
            lines.append("État : vide ou à compléter")
        else:
            lines.append(f"Mots : {response.word_count}")

        preview = _shorten(response.text)
        if preview:
            lines.append(f"Texte : {preview}")
        else:
            lines.append("Texte : —")

    return "\n".join(lines)


def _extract_response_text(source: str) -> str | None:
    match = re.search(
        r"(?is)(?:\*\*)?\s*r[ée]ponse\s*(?:\*\*)?\s*:\s*(.*)",
        source,
    )
    if not match:
        return None

    return match.group(1)


def _clean_response_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.replace("**", "")
    cleaned = cleaned.replace("__", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _is_empty_response(text: str) -> bool:
    stripped = text.strip().lower()
    if not stripped:
        return True

    placeholders = {
        "...",
        "…",
        "?",
        "à compléter",
        "a completer",
        "réponse à compléter",
        "reponse a completer",
        "todo",
    }

    return stripped in placeholders


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\wÀ-ÿ'-]+\b", text))


def _shorten(text: str, max_length: int = 180) -> str:
    if len(text) <= max_length:
        return text

    return text[: max_length - 1].rstrip() + "…"


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
