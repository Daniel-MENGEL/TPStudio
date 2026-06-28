from __future__ import annotations

import re
from pathlib import Path

from tpstudio.models import Section, TPBlock, TPDocument, TPMetadata


class LatexParser:
    r"""Lecteur spécialisé pour les énoncés de TP au format LaTeX Fabert.

    Ce n'est pas un parseur LaTeX généraliste. Il exploite volontairement
    la structure homogène des TP : \objectifs, \materiel, \annexes,
    \indications, \questions, etc.

    Le lecteur n'invente pas d'intention pédagogique. Il extrait uniquement
    les informations explicitement présentes dans le fichier source.
    """

    KNOWN_BLOCKS: dict[str, str] = {
        "objectifs": "Objectifs",
        "materiel": "Matériel",
        "annexes": "Annexes",
        "indications": "Indications",
        "questions": "Questions",
        "rapport": "Rapport",
        "appels": "Appels professeur",
    }

    SECTION_PATTERN = r"\\(?P<command>section|subsection|subsubsection)\*?\{(?P<title>[^{}]*)\}"

    def __init__(self, tex_path: str | Path):
        self.tex_path = Path(tex_path)

    def parse(self) -> TPDocument:
        text = self.tex_path.read_text(encoding="utf-8", errors="replace")
        text = self._strip_comments(text)
        metadata = self._parse_metadata(text)
        metadata.source_tex = self.tex_path
        blocks = self._parse_blocks(text)
        sections = self._parse_sections(text)
        return TPDocument(metadata=metadata, blocks=blocks, sections=sections)

    def _parse_metadata(self, text: str) -> TPMetadata:
        title = self._first_braced(text, "title")
        pdf_slug = self._parse_def(text, "nompdf")
        session_label, tp_code = self._parse_maketitle(text)
        return TPMetadata(
            title=self._clean_latex_inline(title),
            session_label=self._clean_latex_inline(session_label),
            tp_code=self._clean_latex_inline(tp_code),
            pdf_slug=self._clean_latex_inline(pdf_slug),
        )

    def _parse_blocks(self, text: str) -> list[TPBlock]:
        block_positions: list[tuple[int, str]] = []
        boundary_positions: list[int] = []

        for kind in self.KNOWN_BLOCKS:
            for match in re.finditer(rf"\\{kind}\b", text):
                block_positions.append((match.start(), kind))
                boundary_positions.append(match.start())

        for match in re.finditer(self.SECTION_PATTERN, text):
            boundary_positions.append(match.start())

        block_positions.sort()
        boundary_positions = sorted(set(boundary_positions + [len(text)]))

        blocks: list[TPBlock] = []
        for start, kind in block_positions:
            command_match = re.match(rf"\\{kind}\b", text[start:])
            if not command_match:
                continue
            content_start = start + command_match.end()
            content_end = self._next_boundary_after(boundary_positions, start)
            raw = text[content_start:content_end].strip()
            raw = self._trim_at_document_end(raw)
            blocks.append(
                TPBlock(
                    kind=kind,
                    title=self.KNOWN_BLOCKS[kind],
                    raw=raw,
                    items=self._extract_items(raw),
                )
            )
        return blocks

    def _next_boundary_after(self, boundaries: list[int], start: int) -> int:
        for boundary in boundaries:
            if boundary > start:
                return boundary
        return boundaries[-1]

    def _parse_sections(self, text: str) -> list[Section]:
        sections: list[Section] = []
        matches = list(re.finditer(self.SECTION_PATTERN, text))
        for idx, match in enumerate(matches):
            content_start = match.end()
            content_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            raw = self._trim_at_document_end(text[content_start:content_end].strip())
            sections.append(
                Section(
                    title=self._clean_latex_inline(match.group("title")),
                    level=self._section_level(match.group("command")),
                    raw_command=match.group(0),
                    raw=raw,
                    items=self._extract_items(raw),
                )
            )
        return sections

    def _section_level(self, command_name: str) -> int:
        if command_name == "subsubsection":
            return 3
        if command_name == "subsection":
            return 2
        return 1

    def _extract_items(self, raw: str) -> list[str]:
        items: list[str] = []
        parts = re.split(r"\\item\b", raw)
        if len(parts) > 1:
            for part in parts[1:]:
                cleaned = self._clean_latex_inline(part)
                cleaned = cleaned.strip(" .\n\t")
                if cleaned:
                    items.append(cleaned)
            return items

        for line in raw.splitlines():
            cleaned = self._clean_latex_inline(line).strip()
            if cleaned:
                items.append(cleaned)
        return items

    def _first_braced(self, text: str, command: str) -> str:
        match = re.search(rf"\\{command}\s*\{{([^{{}}]*)\}}", text, re.S)
        return match.group(1).strip() if match else ""

    def _parse_def(self, text: str, name: str) -> str:
        match = re.search(rf"\\def\\{name}\s*\{{([^{{}}]*)\}}", text, re.S)
        return match.group(1).strip() if match else ""

    def _parse_maketitle(self, text: str) -> tuple[str, str]:
        match = re.search(r"\\maketitle\s*\{([^{}]*)\}\s*\{([^{}]*)\}", text, re.S)
        if not match:
            return "", ""
        return match.group(1).strip(), match.group(2).strip()

    def _strip_comments(self, text: str) -> str:
        lines: list[str] = []
        for line in text.splitlines():
            lines.append(self._strip_comment_from_line(line))
        return "\n".join(lines)

    def _strip_comment_from_line(self, line: str) -> str:
        escaped = False
        for i, char in enumerate(line):
            if char == "\\" and not escaped:
                escaped = True
                continue
            if char == "%" and not escaped:
                return line[:i]
            escaped = False
        return line

    def _trim_at_document_end(self, raw: str) -> str:
        end_index = raw.find(r"\end{document}")
        if end_index >= 0:
            return raw[:end_index].strip()
        return raw

    def _clean_latex_inline(self, text: str) -> str:
        text = text.replace("~", " ")
        text = text.replace(r"\,", " ")
        text = text.replace(r"\'e", "é").replace(r"\`e", "è")
        text = text.replace(r"\^e", "ê").replace(r"\`a", "à")
        text = text.replace(r"\c c", "ç")
        text = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", text)
        text = re.sub(r"\\emph\{([^{}]*)\}", r"\1", text)
        text = re.sub(r"\\url\{([^{}]*)\}", r"\1", text)
        text = re.sub(r"\\(?:begin|end)\{[^{}]*\}", " ", text)
        text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
        text = text.replace("{", "").replace("}", "")
        text = re.sub(r"\s+", " ", text)
        return text.strip()
