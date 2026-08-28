from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

import nbformat

from tpstudio.glossary import (
    Glossary,
    default_scientific_glossary,
    match_terms,
)

TARGET_SECTION_KINDS = {
    "protocole": "Protocole",
    "objectif": "Objectifs",
    "objectifs": "Objectifs",
    "problematique": "Problématique",
}

WEAK_STATUSES = {"fragile", "à compléter"}


@dataclass(frozen=True)
class PedagogicalSectionFinding:
    cell_index: int
    section_kind: str
    section_title: str
    status: str
    reasons: tuple[str, ...]
    suggestion: str
    source_text: str

    @property
    def is_weak(self) -> bool:
        return self.status in WEAK_STATUSES


def analyze_pedagogical_sections(
    notebook_path: str | Path,
    glossary: Glossary | None = None,
) -> list[PedagogicalSectionFinding]:
    notebook = nbformat.read(Path(notebook_path), as_version=4)
    return analyze_pedagogical_sections_in_notebook(notebook, glossary=glossary)


def analyze_pedagogical_sections_in_notebook(
    notebook,
    glossary: Glossary | None = None,
) -> list[PedagogicalSectionFinding]:
    findings: list[PedagogicalSectionFinding] = []
    glossary = glossary or default_scientific_glossary()

    for cell_index, cell in enumerate(notebook.cells):
        if getattr(cell, "cell_type", "") != "markdown":
            continue

        source = str(getattr(cell, "source", "") or "")

        if _contains_response_marker(source):
            continue

        heading = _first_heading(source)
        if heading is None:
            continue

        title, body = heading
        section_kind = _section_kind(title)

        if section_kind is None:
            continue

        body = _clean_student_text(body)

        if section_kind == "protocole":
            status, reasons, suggestion = _diagnose_protocol(body, glossary=glossary)
        else:
            status, reasons, suggestion = _diagnose_short_written_section(
                body,
                section_kind=section_kind,
            )

        findings.append(
            PedagogicalSectionFinding(
                cell_index=cell_index,
                section_kind=section_kind,
                section_title=title.strip(),
                status=status,
                reasons=tuple(reasons),
                suggestion=suggestion,
                source_text=source,
            )
        )

    return findings


def add_pedagogical_section_feedback_to_notebook(
    copy_path: str | Path,
    corrected_path: str | Path,
) -> int:
    findings = [
        finding
        for finding in analyze_pedagogical_sections(copy_path)
        if finding.is_weak
    ]

    if not findings:
        return 0

    corrected = Path(corrected_path)
    notebook = nbformat.read(corrected, as_version=4)

    inserted = 0

    for finding in findings:
        target_index = _find_matching_cell_index(
            notebook,
            finding.source_text,
        )

        if target_index is None:
            continue

        marker = _feedback_marker(finding)

        if _comment_already_present(notebook, marker):
            continue

        comment = nbformat.v4.new_markdown_cell(
            _format_local_feedback(finding)
        )
        comment.metadata["tpstudio"] = {
            "kind": "pedagogical-section-feedback",
            "section": finding.section_kind,
            "status": finding.status,
        }

        notebook.cells.insert(target_index + 1, comment)
        inserted += 1

    if inserted:
        nbformat.write(notebook, corrected)

    return inserted


def add_pedagogical_section_feedback_to_report(
    copy_path: str | Path,
    report_path: str | Path,
) -> int:
    findings = analyze_pedagogical_sections(copy_path)

    if not findings:
        return 0

    weak = [finding for finding in findings if finding.is_weak]
    report = Path(report_path)
    text = report.read_text(encoding="utf-8")

    if "### Diagnostic des sections pédagogiques" in text:
        return len(weak)

    section = _format_report_section(findings)

    anchor = "### Diagnostic des réponses"

    if anchor in text:
        text = text.replace(
            anchor,
            section + "\n\n" + anchor,
            1,
        )
    else:
        text = text.rstrip() + "\n\n" + section + "\n"

    text = _insert_summary_line(text, weak_count=len(weak))
    text = _increment_local_comment_count(text, increment=len(weak))
    text = _insert_priorities(text, weak)
    text = _insert_advice(text, weak)

    report.write_text(text, encoding="utf-8")
    return len(weak)


def _diagnose_protocol(
    text: str,
    *,
    glossary: Glossary,
) -> tuple[str, list[str], str]:
    if _is_placeholder_or_empty(text):
        return (
            "à compléter",
            ["aucune démarche expérimentale exploitable n'est décrite"],
            (
                "Décrivez le montage, les grandeurs mesurées et les principales "
                "étapes permettant de reproduire la manipulation."
            ),
        )

    normalized = _normalize(text)
    words = _meaningful_words(text)

    action_hits = _count_keyword_families(
        normalized,
        [
            # Racines volontairement courtes pour reconnaître aussi les
            # formes conjuguées : placer/plaçons, aligner/alignons, etc.
            ("plac", "positionn", "orient"),
            ("align", "regl", "ajust"),
            ("mesur", "relev", "not"),
            ("vari", "repet", "chois"),
            ("trac", "calcul", "determin", "report"),
        ],
    )

    scientific_matches = match_terms(text, glossary)
    diagnostic_groups = {
        group
        for match in scientific_matches
        for group in match.term.diagnostic_groups
    }

    if diagnostic_groups:
        physical_hits = len(diagnostic_groups)
    else:
        # Un glossaire personnalisé dépourvu de groupes pédagogiques ne doit
        # pas modifier implicitement la sémantique historique du diagnostic.
        # Les catégories scientifiques (quantity, instrument, etc.) ne sont
        # pas équivalentes aux familles utilisées pour évaluer un protocole.
        physical_hits = _count_keyword_families(
            normalized,
            [
                ("angle", "incidence", "refraction"),
                ("disque", "rapporteur", "laser", "rayon"),
                ("plexiglas", "dioptre"),
                ("mesure", "incertitude", "tableau"),
            ],
        )

    vague = any(
        phrase in normalized
        for phrase in (
            "materiel fourni",
            "materiel qui nous a ete fourni",
            "materiel qui nous a ete fournis",
            "on utilise le materiel",
            "comme indique",
            "comme demande",
            "on fait l experience",
        )
    )

    reasons: list[str] = []

    if len(words) < 12:
        reasons.append("description trop brève")

    if vague:
        reasons.append("formulation trop générale")

    if action_hits < 2:
        reasons.append("étapes expérimentales insuffisamment décrites")

    if physical_hits < 1:
        reasons.append("aucune grandeur ou élément du montage n'est précisé")

    if reasons:
        return (
            "fragile",
            reasons,
            (
                "Précisez le montage, ce qui est réglé ou déplacé, les grandeurs "
                "relevées et l'ordre des principales étapes."
            ),
        )

    if len(words) < 25 or action_hits < 3 or physical_hits < 2:
        return (
            "acceptable",
            ["démarche présente mais encore peu détaillée"],
            (
                "Ajoutez quelques précisions pour qu'un autre groupe puisse "
                "reproduire la manipulation sans explication orale."
            ),
        )

    return (
        "solide",
        ["montage, mesures et étapes principales sont explicités"],
        "",
    )


def _diagnose_short_written_section(
    text: str,
    *,
    section_kind: str,
) -> tuple[str, list[str], str]:
    if _is_placeholder_or_empty(text):
        return (
            "à compléter",
            [f"section {section_kind} non renseignée"],
            f"Rédigez explicitement la section « {section_kind} ».",
        )

    words = _meaningful_words(text)

    if len(words) < 10:
        return (
            "fragile",
            ["contenu trop bref pour expliciter l'idée attendue"],
            (
                "Développez l'idée principale en une ou deux phrases précises "
                "et reliées au TP."
            ),
        )

    if len(words) < 20:
        return (
            "acceptable",
            ["idée présente mais peu développée"],
            "Précisez davantage le lien avec la manipulation réalisée.",
        )

    return (
        "solide",
        ["section suffisamment développée"],
        "",
    )


def _first_heading(source: str) -> tuple[str, str] | None:
    matches = list(
        re.finditer(
            r"(?m)^\s{0,3}#{1,6}\s*(.+?)\s*$",
            source,
        )
    )

    if not matches:
        return None

    match = matches[0]
    title = match.group(1).strip().rstrip(":")
    body = source[match.end():]
    return title, body


def _section_kind(title: str) -> str | None:
    normalized = _normalize(title)

    if "protocole" in normalized:
        return "protocole"

    if "objectif" in normalized:
        return "objectifs"

    if "problematique" in normalized:
        return "problematique"

    return None


def _contains_response_marker(text: str) -> bool:
    return "reponse" in _normalize(text)


def _clean_student_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_`>#-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_placeholder_or_empty(text: str) -> bool:
    normalized = _normalize(text)

    if not normalized:
        return True

    placeholders = {
        "a completer",
        "todo",
        "reponse",
        "votre reponse",
        "...",
        "xxx",
    }

    return normalized in placeholders


def _meaningful_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}", text)


def _count_keyword_families(
    text: str,
    families: list[tuple[str, ...]],
) -> int:
    return sum(
        1
        for family in families
        if any(keyword in text for keyword in family)
    )


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    without_accents = "".join(
        char
        for char in normalized
        if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_accents.casefold().split())


def _find_matching_cell_index(
    notebook,
    source_text: str,
) -> int | None:
    target = source_text.strip()

    for index, cell in enumerate(notebook.cells):
        if getattr(cell, "cell_type", "") != "markdown":
            continue

        if str(getattr(cell, "source", "") or "").strip() == target:
            return index

    return None


def _feedback_marker(
    finding: PedagogicalSectionFinding,
) -> str:
    return (
        "Retour TPStudio — section pédagogique — "
        f"{finding.cell_index} — {finding.section_kind}"
    )


def _comment_already_present(
    notebook,
    marker: str,
) -> bool:
    return any(
        marker in str(getattr(cell, "source", "") or "")
        for cell in notebook.cells
    )


def _format_local_feedback(
    finding: PedagogicalSectionFinding,
) -> str:
    reasons = "; ".join(finding.reasons)
    marker = _feedback_marker(finding)

    if finding.status == "à compléter":
        background = "#fde8e8"
        border = "#c62828"
        label = "À compléter"
    else:
        background = "#fff0e0"
        border = "#ef6c00"
        label = "À revoir"

    return f"""
<div style="background:{background}; border-left:5px solid {border}; padding:12px 14px; border-radius:6px;">

### {finding.section_title}

**{label}** — {reasons}.

**Suggestion :** {finding.suggestion}

</div>

<!-- {marker} -->
""".strip()


def _format_report_section(
    findings: list[PedagogicalSectionFinding],
) -> str:
    counts = {
        "solide": 0,
        "acceptable": 0,
        "fragile": 0,
        "à compléter": 0,
    }

    for finding in findings:
        counts[finding.status] = counts.get(finding.status, 0) + 1

    lines = [
        "### Diagnostic des sections pédagogiques",
        (
            f"- Sections analysées : **{len(findings)}**"
            f" — solides : **{counts['solide']}**,"
            f" acceptables : **{counts['acceptable']}**,"
            f" fragiles : **{counts['fragile']}**,"
            f" à compléter : **{counts['à compléter']}**."
        ),
    ]

    icons = {
        "solide": "✅",
        "acceptable": "🟡",
        "fragile": "⚠️",
        "à compléter": "❌",
    }

    for finding in findings:
        reasons = "; ".join(finding.reasons)
        lines.append(
            f"- {icons.get(finding.status, '•')} "
            f"Cellule {finding.cell_index + 1} — "
            f"partie « {finding.section_title} » : "
            f"**{finding.status}** — {reasons}."
        )

    return "\n".join(lines)


def _insert_summary_line(
    text: str,
    *,
    weak_count: int,
) -> str:
    line = (
        "- Sections pédagogiques fragiles ou à compléter : "
        f"**{weak_count}**."
    )

    if line in text:
        return text

    anchor_pattern = re.compile(
        r"^- Commentaires locaux insérés : \*\*\d+\*\*\.\s*$",
        re.MULTILINE,
    )
    match = anchor_pattern.search(text)

    if match:
        return text[:match.start()] + line + "\n" + text[match.start():]

    return text


def _increment_local_comment_count(
    text: str,
    *,
    increment: int,
) -> str:
    if increment <= 0:
        return text

    pattern = re.compile(
        r"(- Commentaires locaux insérés : \*\*)(\d+)(\*\*\.)"
    )

    def replace(match: re.Match[str]) -> str:
        current = int(match.group(2))
        return (
            match.group(1)
            + str(current + increment)
            + match.group(3)
        )

    return pattern.sub(replace, text, count=1)


def _insert_priorities(
    text: str,
    weak: list[PedagogicalSectionFinding],
) -> str:
    if not weak:
        return text

    header = "### Priorités avant nouveau rendu"
    position = text.find(header)

    if position == -1:
        return text

    line_end = text.find("\n", position)

    if line_end == -1:
        return text

    additions = []

    for finding in weak:
        reasons = "; ".join(finding.reasons)
        bullet = (
            f"- Cellule {finding.cell_index + 1} — partie "
            f"« {finding.section_title} » : section "
            f"**{finding.status}** — {reasons}."
        )

        if bullet not in text:
            additions.append(bullet)

    if not additions:
        return text

    insertion = "\n" + "\n".join(additions)
    return text[:line_end] + insertion + text[line_end:]


def _insert_advice(
    text: str,
    weak: list[PedagogicalSectionFinding],
) -> str:
    if not weak:
        return text

    advice = (
        "- Reprenez les sections pédagogiques signalées comme fragiles "
        "ou à compléter."
    )

    if advice in text:
        return text

    header = "### Conseils ciblés"
    position = text.find(header)

    if position == -1:
        return text

    line_end = text.find("\n", position)

    if line_end == -1:
        return text

    return text[:line_end] + "\n" + advice + text[line_end:]
