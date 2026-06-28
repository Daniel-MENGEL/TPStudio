from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

BlockKind = Literal[
    "objectifs",
    "materiel",
    "annexes",
    "indications",
    "questions",
    "rapport",
    "appels",
    "unknown",
]


@dataclass(slots=True)
class Metadata:
    """Métadonnées générales d'un TP.

    Ces informations décrivent le TP lui-même, indépendamment du format
    d'origine. Elles peuvent venir d'un fichier LaTeX, d'un notebook ou,
    plus tard, d'un fichier de configuration.
    """

    title: str = ""
    session_label: str = ""
    tp_code: str = ""
    pdf_slug: str = ""
    duration: str = ""
    source_tex: Path | None = None
    source_notebook: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "session_label": self.session_label,
            "tp_code": self.tp_code,
            "pdf_slug": self.pdf_slug,
            "duration": self.duration,
            "source_tex": str(self.source_tex) if self.source_tex else None,
            "source_notebook": str(self.source_notebook) if self.source_notebook else None,
        }


@dataclass(slots=True)
class PedagogicalBlock:
    """Bloc pédagogique extrait d'une source de TP.

    Exemples : objectifs, matériel, annexes, indications, questions.
    Le champ ``raw`` conserve le texte original nettoyé au minimum ;
    ``items`` contient une version structurée quand une liste est détectée.
    """

    kind: BlockKind
    title: str
    raw: str = ""
    items: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.raw.strip() and not self.items

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "raw": self.raw,
            "items": list(self.items),
        }


@dataclass(slots=True)
class Section:
    """Partie logique du TP.

    Une section correspond à une partie repérée dans l'énoncé, par exemple
    ``Première méthode`` ou ``Vérification graphique``.

    ``raw`` conserve le contenu LaTeX situé sous le titre. ``items`` contient
    les items de liste détectés dans cette section, ce qui permet déjà
    d'obtenir les questions principales sans interpréter toute la syntaxe
    LaTeX.
    """

    title: str
    level: int = 1
    raw_command: str = ""
    raw: str = ""
    items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "level": self.level,
            "raw_command": self.raw_command,
            "raw": self.raw,
            "items": list(self.items),
        }


@dataclass(slots=True)
class TeacherCall:
    """Marqueur local indiquant un appel professeur dans une consigne.

    Dans les fichiers LaTeX, il correspond à la commande inline ``\appel``.
    Le texte associé est la consigne dans laquelle le marqueur apparaît.
    """

    line: int = 0
    text: str = ""
    section_title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "text": self.text,
            "section_title": self.section_title,
        }


@dataclass(slots=True)
class Figure:
    """Figure référencée par le TP."""

    path: Path | None = None
    caption: str = ""
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path) if self.path else None,
            "caption": self.caption,
            "label": self.label,
        }


@dataclass(slots=True)
class Resource:
    """Ressource associée au TP : annexe, vidéo, image, fichier de données."""

    title: str
    kind: str = "resource"
    path: Path | None = None
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "kind": self.kind,
            "path": str(self.path) if self.path else None,
            "url": self.url,
        }


@dataclass(slots=True)
class TP:
    """Représentation interne d'un TP.

    TPStudio ne manipule pas directement du LaTeX ou du JSON notebook dans
    ses générateurs. Les parseurs remplissent un objet ``TP`` ; les renderers
    s'appuient ensuite sur cet objet.
    """

    metadata: Metadata = field(default_factory=Metadata)
    blocks: list[PedagogicalBlock] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    teacher_calls: list[TeacherCall] = field(default_factory=list)

    def block(self, kind: str) -> PedagogicalBlock | None:
        for block in self.blocks:
            if block.kind == kind:
                return block
        return None

    def block_items(self, kind: str) -> list[str]:
        block = self.block(kind)
        return list(block.items) if block else []

    @property
    def title(self) -> str:
        return self.metadata.title

    @property
    def objectives(self) -> list[str]:
        return self.block_items("objectifs")

    @property
    def equipment(self) -> list[str]:
        return self.block_items("materiel")

    @property
    def annexes(self) -> list[str]:
        return self.block_items("annexes")

    @property
    def indications(self) -> list[str]:
        return self.block_items("indications")

    @property
    def questions(self) -> list[str]:
        return self.block_items("questions")

    def summary(self) -> str:
        """Retourne un résumé court, utile en diagnostic et en tests manuels."""

        return (
            f"TP(title={self.title!r}, "
            f"objectives={len(self.objectives)}, "
            f"equipment={len(self.equipment)}, "
            f"sections={len(self.sections)}, "
            f"questions={len(self.questions)}, "
            f"teacher_calls={len(self.teacher_calls)})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "sections": [section.to_dict() for section in self.sections],
            "blocks": [block.to_dict() for block in self.blocks],
            "figures": [figure.to_dict() for figure in self.figures],
            "resources": [resource.to_dict() for resource in self.resources],
            "teacher_calls": [call.to_dict() for call in self.teacher_calls],
        }


# Aliases de transition : ils gardent compatible le code A2 pendant que
# le vocabulaire interne se stabilise autour de TP / Metadata / PedagogicalBlock.
TPMetadata = Metadata
TPBlock = PedagogicalBlock
TPDocument = TP
