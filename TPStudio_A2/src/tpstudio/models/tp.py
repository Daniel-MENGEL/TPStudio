from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TPBlock:
    """Bloc pédagogique extrait d'un énoncé LaTeX normalisé."""

    kind: str
    title: str
    raw: str
    items: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TPMetadata:
    """Métadonnées générales du TP."""

    title: str = ""
    session_label: str = ""
    tp_code: str = ""
    pdf_slug: str = ""
    source_tex: Path | None = None


@dataclass(slots=True)
class TPDocument:
    """Représentation interne d'un TP issue du fichier .tex."""

    metadata: TPMetadata
    blocks: list[TPBlock] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)

    def block(self, kind: str) -> TPBlock | None:
        for block in self.blocks:
            if block.kind == kind:
                return block
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": {
                "title": self.metadata.title,
                "session_label": self.metadata.session_label,
                "tp_code": self.metadata.tp_code,
                "pdf_slug": self.metadata.pdf_slug,
                "source_tex": str(self.metadata.source_tex) if self.metadata.source_tex else None,
            },
            "sections": self.sections,
            "blocks": [
                {
                    "kind": block.kind,
                    "title": block.title,
                    "items": block.items,
                    "raw": block.raw,
                }
                for block in self.blocks
            ],
        }
