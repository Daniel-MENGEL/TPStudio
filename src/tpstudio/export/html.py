"""Pure HTML rendering of an already annotated notebook."""

from __future__ import annotations

from copy import deepcopy
import nbformat
import re
from html import escape
from nbformat.notebooknode import NotebookNode
from nbconvert import HTMLExporter

from tpstudio.annotation.rendering import annotation_css

from .model import CopyExportOptions


_DEFAULT_TITLE = "Copie corrigée"
_STYLE = "<style>.tpstudio-banner{padding:0.8em;margin:0 0 1.2em;border:1px solid #ccd;background:#f7f8fa}.tpstudio-banner strong{display:block;margin-bottom:.25em}</style>" + annotation_css()
_BANNER = "<div class=\"tpstudio-banner\"><strong>Copie corrigée</strong>Document généré en lecture seule. Les commentaires ont été validés par le professeur.</div>"
_MARKDOWN_ATTACHMENT = re.compile(
    r"!\[(?P<label>[^\]]*)\]\(attachment:(?P<name>[^)]*)\)"
)
_DIV_TAG = re.compile(r"<\s*(?P<closing>/?)\s*div\b[^>]*>", re.IGNORECASE)


def _remove_unmatched_closing_divs(source: str) -> str:
    """Remove stray ``</div>`` tags without rewriting student content.

    Student notebook templates keep each styled answer block in one Markdown
    cell.  An accidental second closing tag can make nbconvert close one of its
    own layout containers and leave a very large blank area in the preview.
    """

    depth = 0
    pieces: list[str] = []
    cursor = 0
    for match in _DIV_TAG.finditer(source):
        pieces.append(source[cursor:match.start()])
        if match.group("closing"):
            if depth:
                depth -= 1
                pieces.append(match.group(0))
        else:
            depth += 1
            pieces.append(match.group(0))
        cursor = match.end()
    pieces.append(source[cursor:])
    return "".join(pieces)


def _sanitize_notebook_for_html(notebook: NotebookNode) -> NotebookNode:
    """Make incomplete attachments and malformed answer HTML safe to render."""

    sanitized = deepcopy(notebook)
    for cell in sanitized.cells:
        if cell.cell_type != "markdown":
            continue
        attachments = cell.get("attachments", {})

        def replace_missing(match: re.Match[str]) -> str:
            if match.group("name") in attachments:
                return match.group(0)
            label = match.group("label").strip()
            detail = f" — {label}" if label else ""
            return f"*Image non insérée{detail}.*"

        source = cell.source
        if not isinstance(source, str):
            source = "".join(source)
        source = _MARKDOWN_ATTACHMENT.sub(replace_missing, source)
        cell.source = _remove_unmatched_closing_divs(source)
    return sanitized


def _customize_nbconvert_html(document: str, *, title: str = _DEFAULT_TITLE) -> str:
    """Inject A71f presentation into the one nbconvert document."""
    if not isinstance(document, str) or not document.strip():
        raise ValueError("Le document HTML nbconvert est vide.")
    if not re.search(r"<html\b", document, re.IGNORECASE) or not re.search(r"</html\s*>", document, re.IGNORECASE):
        raise ValueError("Le rendu nbconvert ne contient pas un document HTML complet.")
    if not re.search(r"<head\b", document, re.IGNORECASE) or not re.search(r"</head\s*>", document, re.IGNORECASE):
        raise ValueError("Le rendu nbconvert ne contient pas d'en-tête HTML.")
    if not re.search(r"<body\b[^>]*>", document, re.IGNORECASE) or not re.search(r"</body\s*>", document, re.IGNORECASE):
        raise ValueError("Le rendu nbconvert ne contient pas de corps HTML.")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Le titre HTML ne peut pas être vide.")
    document = re.sub(r"<title\b[^>]*>.*?</title\s*>", "", document, flags=re.IGNORECASE | re.DOTALL)
    document = re.sub(r"</head\s*>", f"<title>{escape(title)}</title>\n{_STYLE}\n</head>", document, count=1, flags=re.IGNORECASE)
    if 'class="tpstudio-banner"' not in document:
        document = re.sub(r"(<body\b[^>]*>)", r"\1" + _BANNER, document, count=1, flags=re.IGNORECASE)
    return document


def render_annotated_notebook_html(
    notebook: NotebookNode,
    *,
    options: CopyExportOptions,
    title: str = _DEFAULT_TITLE,
) -> str:
    if not isinstance(notebook, NotebookNode):
        raise TypeError("Le notebook doit être un NotebookNode.")
    if type(options) is not CopyExportOptions:
        raise TypeError("Les options d'export sont invalides.")
    nbformat.validate(notebook)
    renderable_notebook = _sanitize_notebook_for_html(notebook)
    exporter = HTMLExporter(template_name="lab")
    exporter.exclude_input = not options.include_code
    exporter.exclude_output = not options.include_outputs
    exporter.exclude_input_prompt = not options.include_input_prompts
    exporter.exclude_output_prompt = not options.include_output_prompts
    resources = {"embed_images": options.embed_images}
    body, _ = exporter.from_notebook_node(renderable_notebook, resources=resources)
    return _customize_nbconvert_html(body, title=title)
