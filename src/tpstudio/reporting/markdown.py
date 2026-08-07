"""Markdown and console rendering for immutable teacher reports."""

from __future__ import annotations

from tpstudio.feedback import FeedbackAudience

from .priorities import TeacherReportSeverity
from .teacher_report import TeacherCopyReport


_MARK = {
    TeacherReportSeverity.BLOCKING: "❌",
    TeacherReportSeverity.IMPORTANT: "⚠️",
    TeacherReportSeverity.ATTENTION: "🟡",
    TeacherReportSeverity.INFO: "ℹ️",
}


def _shown(value: object | None) -> str:
    return "—" if value is None else str(value)


def render_teacher_report_markdown(report: TeacherCopyReport) -> str:
    if type(report) is not TeacherCopyReport:
        raise TypeError("Le renderer exige exactement un TeacherCopyReport.")
    o, t = report.overview, report.technical
    lines = [
        f"# Rapport TPStudio — {report.title}", "", "## Retour TPStudio", "",
        "Rapport automatique en lecture seule, fondé sur l’état enregistré du notebook. TPStudio n’a exécuté aucun code. Ce document aide la revue professeur et ne produit aucune note automatique.", "",
        "## Synthèse rapide", "",
        f"- Projet : `{report.project_id}`", f"- Source : `{report.source_id}`",
        f"- Productions : {o.resolved_productions} résolues, {o.missing_productions} absentes, {o.ambiguous_productions} ambiguës",
        f"- Diagnostics : {o.diagnostic_count}", f"- Revue humaine requise : {'oui' if o.requires_human_review else 'non'}", "",
        f"- Quantités : {o.evaluable_quantity_count} évaluables, {o.non_evaluable_quantity_count} non évaluables",
        f"- Technique : {o.technical_error_count} erreur(s) enregistrée(s), {o.placeholder_count} placeholder(s)",
        f"- Limitations déclarées : {o.limitation_count}", "",
        "## Priorités de revue", "",
    ]
    lines.extend(
        f"- {_MARK[item.severity]} **{item.severity.value.upper()} — {item.title}** : {item.message}"
        for item in report.priorities
    )
    if not report.priorities: lines.append("- Aucune priorité automatique.")
    lines += ["", "## État technique et exécution enregistrée", "",
        f"- Notebook valide : {'oui' if t.notebook_valid else 'non'} (nbformat {t.nbformat_version})",
        f"- Cellules : {t.cell_count} ({t.markdown_cell_count} Markdown, {t.code_cell_count} code, {t.raw_cell_count} raw)",
        f"- Code non exécuté : {list(t.unexecuted_code_cell_indices)}",
        f"- Erreurs enregistrées : {list(t.error_output_cell_indices)}",
        f"- Marqueurs `?` dans le code : {list(t.placeholder_cell_indices)}",
        f"- Outputs enregistrés : {list(t.stored_output_cell_indices)}",
        f"- Références à des chemins externes détectées : {t.external_path_reference_count}",
        "- TPStudio n’a pas exécuté le notebook.", "", "## Productions attendues", "",
    ]
    lines.extend(f"- `{p.production_id}` — {p.title} : **{p.status}**, cellule(s) {list(p.cell_indices) or '—'}" for p in report.productions)
    lines += ["", "## Valeurs observées", ""]
    for item in report.values:
        selected = "aucune valeur retenue" if item.value is None else f"{item.value} {_shown(item.unit)} via {item.source}"
        lines.append(f"- `{item.production_id}` : **{item.status}**, {selected}, {item.evidence_count} preuve(s), cellule {_shown(item.cell_index)}")
    lines += ["", "## Résultats quantitatifs", ""]
    lines.extend(f"- `{q.production_id}` : {q.status}, évaluable={'oui' if q.evaluable else 'non'}, valeur={_shown(q.value)}, unité={_shown(q.unit)}, incertitude={_shown(q.uncertainty)}, raisons={list(q.reasons) or '—'}" for q in report.quantities)
    lines += ["", "## Relations scientifiques", ""]
    lines.extend(f"- `{r.relation_id}` : {r.status}, cellule(s) {list(r.cell_indices) or '—'}" for r in report.relations)
    lines += ["", "## Graphe et régression", "", "Attendu Snell-Descartes : x = `sin(i2)`, y = `sin(i1)`, pente `a = n`. L’apparence et les pixels ne sont pas inspectés.", ""]
    for g in report.graph:
        lines += [f"### `{g.production_id}`", "", f"- Cellule : {_shown(g.cell_index)} ; figure enregistrée : {'oui' if g.figure_output_present else 'non'}", f"- x / y observés : `{_shown(g.x_expression)}` / `{_shown(g.y_expression)}`", f"- labels : `{_shown(g.x_label)}` / `{_shown(g.y_label)}`", f"- orientation : {g.orientation_status} ; labels : {g.label_status} ; régression : {g.regression_status} ; pente–indice : {g.slope_relation_status}", f"- Limites : {list(g.limitations) or '—'}", ""]
    lines += ["## Comparaisons quantitatives", ""]
    for index, c in enumerate(report.comparisons, 1):
        lines += [f"### Comparaison {index} — `{c.comparison_id}`", "", f"- Résultats comparés : `{c.left_quantity_id}` / `{c.right_quantity_id}`", f"- En objectif : {_shown(c.normalized_error)} ; classe A70b : **{c.objective_status}** ; raisons : {list(c.objective_reasons) or '—'}", f"- En étudiant : {_shown(c.student_error_value)} ; statut A70d : **{_shown(c.student_error_status)}**", f"- Interprétation A70e : **{_shown(c.interpretation_status)}** ; preuve : {_shown(c.interpretation_excerpt)}", f"- Justification A70g : **{_shown(c.justification_status)}** ; observés={list(c.observed_justification_elements)} ; REQUIRED manquants={list(c.missing_required_elements)} ; groupes manquants={list(c.missing_alternative_groups)}", ""]
    f = report.final_conclusion
    lines += ["## Conclusion finale", "", f"- Production `{f.production_id}` : **{f.status}**", f"- Cellule(s) : {list(f.cell_indices) or '—'}", f"- Texte présent : {'oui' if f.has_text else 'non'}", "- Cette conclusion reste distincte des interprétations des comparaisons.", "", "## Diagnostics", ""]
    lines.extend(f"- `{d.diagnostic_id}` [{d.category.value}/{d.severity.value}] `{d.code}` — {d.message_key}" for d in report.diagnostics)
    if not report.diagnostics: lines.append("- Aucun diagnostic produit.")
    lines += ["", "## Retours configurés", "", "### Pour le professeur", ""]
    teacher = tuple(item for item in report.feedback if item.audience is FeedbackAudience.TEACHER)
    student = tuple(item for item in report.feedback if item.audience is FeedbackAudience.STUDENT)
    lines.extend(f"- {item.text}" for item in teacher)
    if not teacher: lines.append("- Aucun retour professeur configuré produit.")
    lines += ["", "### Pour l’étudiant", ""]
    lines.extend(f"- {item.text}" for item in student)
    if not student: lines.append("- Aucun retour étudiant configuré produit.")
    lines += ["", "## Conseils ciblés", ""]
    for text in dict.fromkeys(item.text for item in student): lines.append(f"- {text}")
    if not student: lines.append("- Aucun conseil supplémentaire : cette section reprend uniquement les feedbacks configurés.")
    lines += ["", "## Limites de l’analyse", ""]
    lines.extend(f"- {item}" for item in report.limitations)
    if not report.limitations: lines.append("- Aucune limitation déclarée.")
    lines += ["", "## Revue humaine", "", f"- Requise : **{'oui' if report.human_review.required else 'non'}**", f"- Raisons : {list(report.human_review.reasons) or '—'}", f"- Catégories : {[item.value for item in report.human_review.categories] or '—'}", ""]
    return "\n".join(lines)


def summarize_teacher_report(report: TeacherCopyReport) -> str:
    if type(report) is not TeacherCopyReport:
        raise TypeError("Le résumé exige exactement un TeacherCopyReport.")
    o = report.overview
    return "\n".join((
        f"Project: {report.project_id}", f"Source: {report.source_id}",
        f"Productions: {o.resolved_productions}/{len(report.productions)} resolved, {o.missing_productions} missing, {o.ambiguous_productions} ambiguous",
        f"Technical: {o.technical_error_count} stored errors, {o.placeholder_count} placeholders",
        f"Graph: {o.graph_issue_count} issue(s)", f"Comparisons: {len(report.comparisons)}, {o.comparison_issue_count} issue(s)",
        f"Diagnostics: {o.diagnostic_count}", f"Feedback: teacher={o.teacher_feedback_count}, student={o.student_feedback_count}",
        f"Human review: {'YES' if o.requires_human_review else 'NO'}",
    ))
