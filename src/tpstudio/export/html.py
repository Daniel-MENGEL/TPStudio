"""Pure HTML rendering of an already annotated notebook."""

from __future__ import annotations

import nbformat
import re
from nbformat.notebooknode import NotebookNode
from nbconvert import HTMLExporter

from tpstudio.annotation.rendering import annotation_css

from .model import CopyExportOptions


_TITLE = "TPStudio — Lois de Snell-Descartes — Correction"
_STYLE = "<style>.tpstudio-banner{padding:0.8em;margin:0 0 1.2em;border:1px solid #ccd;background:#f7f8fa}.tpstudio-banner strong{display:block;margin-bottom:.25em}</style>" + annotation_css()
_BANNER = "<div class=\"tpstudio-banner\"><strong>TPStudio — copie annotée</strong>Générée en lecture seule ; le notebook n'a pas été exécuté. Les annotations proviennent de la configuration professeur. Aucune note automatique.</div>"


def _customize_nbconvert_html(document: str) -> str:
    """Inject A71f presentation into the one nbconvert document."""
    if not isinstance(document, str) or not document.strip():
        raise ValueError("Le document HTML nbconvert est vide.")
    if not re.search(r"<html\b", document, re.IGNORECASE) or not re.search(r"</html\s*>", document, re.IGNORECASE):
        raise ValueError("Le rendu nbconvert ne contient pas un document HTML complet.")
    if not re.search(r"<head\b", document, re.IGNORECASE) or not re.search(r"</head\s*>", document, re.IGNORECASE):
        raise ValueError("Le rendu nbconvert ne contient pas d'en-tête HTML.")
    if not re.search(r"<body\b[^>]*>", document, re.IGNORECASE) or not re.search(r"</body\s*>", document, re.IGNORECASE):
        raise ValueError("Le rendu nbconvert ne contient pas de corps HTML.")
    document = re.sub(r"<title\b[^>]*>.*?</title\s*>", "", document, flags=re.IGNORECASE | re.DOTALL)
    document = re.sub(r"</head\s*>", f"<title>{_TITLE}</title>\n{_STYLE}\n</head>", document, count=1, flags=re.IGNORECASE)
    if 'class="tpstudio-banner"' not in document:
        document = re.sub(r"(<body\b[^>]*>)", r"\1" + _BANNER, document, count=1, flags=re.IGNORECASE)
    return document


def render_annotated_notebook_html(
    notebook: NotebookNode,
    *,
    options: CopyExportOptions,
) -> str:
    if not isinstance(notebook, NotebookNode):
        raise TypeError("Le notebook doit être un NotebookNode.")
    if type(options) is not CopyExportOptions:
        raise TypeError("Les options d'export sont invalides.")
    nbformat.validate(notebook)
    exporter = HTMLExporter(template_name="lab")
    exporter.exclude_input = not options.include_code
    exporter.exclude_output = not options.include_outputs
    exporter.exclude_input_prompt = not options.include_input_prompts
    exporter.exclude_output_prompt = not options.include_output_prompts
    resources = {"embed_images": options.embed_images}
    body, _ = exporter.from_notebook_node(notebook, resources=resources)
    return _customize_nbconvert_html(body)
