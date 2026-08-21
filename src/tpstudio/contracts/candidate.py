"""Deterministic, non-active candidates extracted from a TP statement."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
import re
from typing import Any

from tpstudio.parsers import LatexParser


class CandidateKind(str, Enum):
    QUANTITY = "quantity"
    RELATION = "relation"
    GRAPH = "graph"
    COMPARISON = "comparison"
    PROTOCOL = "protocol"
    CONSTRAINT = "constraint"
    INTERPRETATION = "interpretation"
    CONCLUSION = "conclusion"
    REFERENCE = "reference"


class CandidateExtractionMode(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"


class CandidateConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class CandidateItem:
    """One neutral statement candidate.

    ``scientific_symbol`` names the candidate's own result (for example
    ``E_n``), while ``target_symbols`` names the operands or quantities an
    action concerns.  An inferred result may therefore legitimately have no
    target symbols when the statement does not identify its operands.
    """
    candidate_id: str
    kind: CandidateKind
    source_document: str
    source_location: tuple[int, int]
    source_text: str
    normalized_text: str
    extraction_mode: CandidateExtractionMode
    confidence: CandidateConfidence
    scientific_symbol: str | None = None
    target_symbols: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("candidate_id", "source_document", "source_text", "normalized_text"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} doit être une chaîne non vide.")
        if type(self.kind) is not CandidateKind:
            raise TypeError("kind doit être un CandidateKind.")
        if type(self.extraction_mode) is not CandidateExtractionMode:
            raise TypeError("extraction_mode doit être un CandidateExtractionMode.")
        if type(self.confidence) is not CandidateConfidence:
            raise TypeError("confidence doit être un CandidateConfidence.")
        if self.scientific_symbol is not None and (
            not isinstance(self.scientific_symbol, str) or not self.scientific_symbol.strip()
        ):
            raise TypeError("scientific_symbol doit être une chaîne ou None.")
        if (
            not isinstance(self.source_location, tuple)
            or len(self.source_location) != 2
            or any(type(value) is not int or value < 1 for value in self.source_location)
            or self.source_location[1] < self.source_location[0]
        ):
            raise ValueError("source_location doit être un intervalle de lignes valide.")
        targets = tuple(self.target_symbols)
        if any(not isinstance(value, str) or not value.strip() for value in targets):
            raise TypeError("target_symbols doit contenir des chaînes non vides.")
        if len(targets) != len(set(targets)):
            raise ValueError("target_symbols doit être sans doublon.")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata doit être un dictionnaire.")
        object.__setattr__(self, "target_symbols", targets)
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class CandidateScientificContract:
    statement_id: str
    source_document: str
    items: tuple[CandidateItem, ...] = ()

    def __post_init__(self) -> None:
        for name in ("statement_id", "source_document"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} doit être une chaîne non vide.")
        items = tuple(self.items)
        if any(type(item) is not CandidateItem for item in items):
            raise TypeError("Chaque élément doit être un CandidateItem.")
        ids = tuple(item.candidate_id for item in items)
        if len(ids) != len(set(ids)):
            raise ValueError("Les candidate_id doivent être uniques.")
        if any(item.source_document != self.source_document for item in items):
            raise ValueError("Les candidats doivent partager le document source.")
        object.__setattr__(self, "items", items)

    def by_kind(self, kind: CandidateKind) -> tuple[CandidateItem, ...]:
        if type(kind) is not CandidateKind:
            raise TypeError("kind doit être un CandidateKind.")
        return tuple(item for item in self.items if item.kind is kind)


def _clean(text: str) -> str:
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .\n\t")


def _symbol(value: str) -> str:
    value = value.strip().strip("$")
    value = re.sub(r"\\(?:mathrm|text|operatorname)\s*", "", value)
    value = re.sub(r"\\([A-Za-z]+)", r"\1", value)
    value = re.sub(r"\s+", "", value)
    return value


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value or "item"


def _line_fragment(lines: list[str], line: int) -> str:
    if 1 <= line <= len(lines):
        return lines[line - 1].rstrip("\n")
    raise ValueError("La ligne source demandée est introuvable.")


def _find_line(lines: list[str], pattern: str, start: int = 0) -> int:
    compiled = re.compile(pattern, re.IGNORECASE)
    for index in range(start, len(lines)):
        if compiled.search(lines[index]):
            return index + 1
    raise ValueError(f"Fragment TeX introuvable pour le motif {pattern!r}.")


def _symbols(text: str) -> tuple[str, ...]:
    values = []
    for raw in re.findall(r"\$([^$]+)\$", text):
        value = _symbol(raw)
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value) and value not in values:
            values.append(value)
    return tuple(values)


def _relation_fragments(text: str) -> tuple[str, ...]:
    """Return non-trivial equalities from explicit TeX math fragments."""
    pattern = re.compile(
        r"\$\$(?P<display>.*?)\$\$"
        r"|\$(?P<inline>[^$]+?)\$"
        r"|\\\((?P<paren>.*?)\\\)"
        r"|\\\[(?P<bracket>.*?)\\\]"
    )
    fragments = []
    for match in pattern.finditer(text):
        fragment = next(value for value in match.groups() if value is not None)
        if "=" not in fragment:
            continue
        left, right = fragment.split("=", 1)
        # Require symbolic expressions on both sides, excluding metadata or
        # numeric assignments while remaining independent of the symbols used.
        if not re.search(r"[A-Za-z\\]", left) or not re.search(r"[A-Za-z\\]", right):
            continue
        fragments.append(fragment)
    return tuple(fragments)


def _make(
    *,
    kind: CandidateKind,
    line: int,
    source_document: str,
    lines: list[str],
    normalized_text: str | None = None,
    scientific_symbol: str | None = None,
    target_symbols: tuple[str, ...] = (),
    confidence: CandidateConfidence = CandidateConfidence.HIGH,
    mode: CandidateExtractionMode = CandidateExtractionMode.EXPLICIT,
    metadata: dict[str, Any] | None = None,
) -> CandidateItem:
    source_text = _line_fragment(lines, line)
    descriptor = _slug(scientific_symbol or (metadata or {}).get("descriptor", kind.value))
    candidate_id = f"{kind.value}-{descriptor}-line-{line}"
    return CandidateItem(
        candidate_id,
        kind,
        source_document,
        (line, line),
        source_text,
        normalized_text or _clean(source_text),
        mode,
        confidence,
        scientific_symbol,
        target_symbols,
        metadata or {},
    )


def extract_candidate_scientific_contract(source: str | Path) -> CandidateScientificContract:
    """Extract conservative, TP-neutral candidates from a Fabert TeX statement."""

    path = Path(source)
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()
    document = LatexParser(path).parse()
    source_document = path.name
    items: list[CandidateItem] = []
    seen: set[str] = set()

    def add(item: CandidateItem) -> None:
        """Add deterministically, preserving distinct same-line candidates."""
        base = item.candidate_id
        candidate_id = base
        ordinal = 2
        while candidate_id in seen:
            candidate_id = f"{base}-{ordinal}"
            ordinal += 1
        if candidate_id != item.candidate_id:
            item = replace(item, candidate_id=candidate_id)
        items.append(item)
        seen.add(candidate_id)

    question_lines = []
    for index, line in enumerate(lines):
        if line.lstrip().startswith("%"):
            continue
        question_lines.extend((index + 1, line) for _ in re.finditer(r"\\item", line))
    for line_number, line in question_lines:
        lowered = line.casefold()
        symbols = _symbols(line)
        if re.search(r"\bmesurer\b|\bmesure de\b|\bd[ée]terminer\b|\bd[ée]duire\b", lowered):
            for symbol in symbols:
                add(_make(kind=CandidateKind.QUANTITY, line=line_number, source_document=source_document,
                           lines=lines, scientific_symbol=symbol, normalized_text=f"Quantité {symbol} demandée.",
                           metadata={"verb": "measure_or_determine"}))
        if "protocole" in lowered:
            add(_make(kind=CandidateKind.PROTOCOL, line=line_number, source_document=source_document,
                      lines=lines, metadata={"descriptor": "protocol"}))
        match = re.search(r"(\d+)\s+valeurs", lowered)
        if match:
            add(_make(kind=CandidateKind.CONSTRAINT, line=line_number, source_document=source_document,
                      lines=lines, metadata={"descriptor": "sample-count", "sample_count_exact": int(match.group(1))}))
        match = re.search(r"au moins\s+(\d+)\s+points", lowered)
        if match:
            add(_make(kind=CandidateKind.CONSTRAINT, line=line_number, source_document=source_document,
                      lines=lines, metadata={"descriptor": "sample-count", "sample_count_min": int(match.group(1))}))
        if "régression linéaire" in lowered:
            add(_make(kind=CandidateKind.GRAPH, line=line_number, source_document=source_document,
                      lines=lines, metadata={"descriptor": "regression", "model": "AFFINE",
                                             "mentioned_symbols": symbols}))
        if "indiquer les unités" in lowered:
            add(_make(kind=CandidateKind.CONSTRAINT, line=line_number, source_document=source_document,
                      lines=lines, target_symbols=symbols,
                      metadata={"descriptor": "units", "unit_required": True}))
        if "comparer" in lowered:
            add(_make(kind=CandidateKind.COMPARISON, line=line_number, source_document=source_document,
                      lines=lines, target_symbols=symbols,
                      metadata={"descriptor": "comparison"}))
            if "écart normalisé" in lowered or "ecart normalise" in lowered:
                add(_make(kind=CandidateKind.QUANTITY, line=line_number, source_document=source_document,
                          lines=lines, scientific_symbol="E_n", target_symbols=symbols,
                          metadata={"descriptor": "normalized-error", "derived_quantity_role": "normalized_error",
                                    "symbol_inferred": True}))

    # Equations are scientific context, not automatically student work. Scan
    # the whole statement, while excluding operational instructions whose
    # equalities describe a manipulation rather than a model.
    for line_number, line in enumerate(lines, 1):
        lowered = line.casefold()
        if line.lstrip().startswith("%"):
            continue
        if any(word in lowered for word in (
            "retirer", "remonter", "accrocher", "tourner", "placer",
            "déplacer", "deplacer", "relever", "régler", "regler",
        )):
            continue
        fragments = _relation_fragments(line)
        for fragment in fragments:
            add(_make(kind=CandidateKind.RELATION, line=line_number,
                      source_document=source_document, lines=lines,
                      confidence=CandidateConfidence.MEDIUM,
                      metadata={"relation_role": "provided_scientific_context",
                                "student_expectation_validated": False,
                                "relation_fragment": fragment}))

    return CandidateScientificContract(path.stem, source_document, tuple(items))
