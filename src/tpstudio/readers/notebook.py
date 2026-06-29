from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tpstudio.models import Notebook, NotebookCell


class NotebookReader:
    """Lecteur minimal de notebooks Jupyter `.ipynb`.

    Le notebook est un fichier JSON. Pour commencer, TPStudio lit seulement
    les cellules, leur type et leur source. Aucune cellule n'est exécutée,
    modifiée ou corrigée à cette étape.
    """

    def __init__(self, notebook_path: str | Path):
        self.notebook_path = Path(notebook_path)

    def parse(self) -> Notebook:
        data = json.loads(self.notebook_path.read_text(encoding="utf-8"))
        cells: list[NotebookCell] = []
        for index, raw_cell in enumerate(data.get("cells", []), start=1):
            cells.append(self._parse_cell(index, raw_cell))
        return Notebook(path=self.notebook_path, cells=cells)

    def _parse_cell(self, index: int, raw_cell: dict[str, Any]) -> NotebookCell:
        source = raw_cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        elif source is None:
            source = ""

        return NotebookCell(
            index=index,
            cell_type=str(raw_cell.get("cell_type", "unknown")),
            source=str(source),
            execution_count=raw_cell.get("execution_count"),
        )
