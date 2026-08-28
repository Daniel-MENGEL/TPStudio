"""A72a local Streamlit application: prepare, never run, a batch."""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from datetime import datetime, timezone
import os

from tpstudio.batch import BatchCopyStatus, render_batch_report_markdown
from tpstudio.export import CopyExportOptions
from tpstudio.orchestration import BatchCopyDispatchStatus
from tpstudio.semantic_analysis import (
    DEFAULT_OPENAI_SEMANTIC_MODEL,
    OpenAISemanticAnalysisProvider,
)
from tpstudio.web.execution import analyze_selected_copy, can_run_batch, export_active_copies, run_selected_dispatch
from tpstudio.web.model import WebBatchOptions
from tpstudio.web.identity import (
    CopyIdentityStatus, StudentIdentity, confirm_copy_identity,
    identify_selected_copy,
)
from tpstudio.web.model import WebCopyOverride
from tpstudio.web.planning import WebInputError, build_batch_plan_from_web_selection, build_dispatch_requests_from_web_selection, resolve_output_dir
from tpstudio.projects import project_descriptor
from tpstudio.projects import (
    FIRST_LAB_FORMATIVE_GRADING_PROFILE,
    suggest_first_lab_rubric,
)
from tpstudio.grading import (
    RubricDecision,
    RubricLevel,
    build_formative_grade_proposal,
)
from tpstudio.web.presenters import (
    batch_plan_rows, graph_summary_rows,
    identity_resolution_candidates, active_analysis_for_source, batch_dispatch_rows,
    project_choices_for_source, exportable_count, non_exportable_count,
    semantic_response_rows,
)
from tpstudio.web.roster import (
    default_roster_path, load_roster, parse_roster_csv, save_roster,
    suggest_roster_students,
)
from tpstudio.web.presenters import review_prefill, select_interpretation_review_items
from tpstudio.web.scientific_overview import (
    build_teacher_scientific_overview, scientific_detail_widget_key,
    scientific_severity_icon,
)
from tpstudio.interpretation import InterpretationClassification
from tpstudio.review_store import append_interpretation_review, review_store_path
from tpstudio.review_store import load_interpretation_reviews
from tpstudio.review_corpus import (
    build_interpretation_review_corpus, interpretation_review_corpus_jsonl,
    load_or_create_corpus_pseudonym_key, summarize_interpretation_review_corpus,
)
from tpstudio.web.state import (
    PLAN_KEY, SELECTION_KEY, SIGNATURE_KEY, WORKSPACE_KEY,
    UPLOADER_GENERATION_KEY, clear_prepared_batch, initialize_session_state,
    invalidate_if_signature_changed, reset_web_session, set_prepared_batch,
    clear_run_result, get_current_run_result, set_run_result, RUN_IN_PROGRESS_KEY,
    default_output_dir,
    REVIEW_FILTER_KEY, REVIEW_INDEX_KEY, REVIEW_MESSAGE_KEY,
    get_current_dispatch_result, set_dispatch_result, clear_dispatch_result,
    invalidate_dispatch_if_signature_changed,
    get_project_overrides, set_project_override, remove_project_override,
    get_export_results, set_export_results,
    SEMANTIC_ANALYSIS_ENABLED_KEY,
)
from tpstudio.web.workspace import WebWorkspace


def _input_signature(copies, output_dir: Path, options: WebBatchOptions) -> tuple:
    return tuple((item.source_id, item.original_filename, item.content_sha256,
                  getattr(getattr(item, "identity", None), "status", None),
                  tuple(getattr(getattr(item, "identity", None), "students", ()))) for item in copies), str(output_dir), options


def _analysis_signature(input_signature: tuple, semantic_enabled: bool, model: str) -> tuple:
    """Signature for analysis results; planning remains independent of AI."""
    return input_signature, bool(semantic_enabled), model


def _semantic_model() -> str:
    return os.getenv("TPSTUDIO_OPENAI_MODEL") or DEFAULT_OPENAI_SEMANTIC_MODEL


_RUBRIC_LEVEL_LABELS = {
    RubricLevel.ABSENT: "Absent",
    RubricLevel.PARTIAL: "Partiel",
    RubricLevel.SATISFACTORY: "Satisfaisant",
    RubricLevel.VERY_GOOD: "Très bien",
}


def _render_first_lab_grading(st, analysis, source_id: str) -> None:
    """Render a teacher-only, non-exported formative grading experiment."""

    profile = FIRST_LAB_FORMATIVE_GRADING_PROFILE
    if analysis.project_id != profile.project_id:
        return
    st.markdown("### Proposition de note formative")
    st.caption(
        "Première séance : base 15/20. Cette proposition dépend uniquement des "
        "niveaux choisis par l’enseignant et n’est pas ajoutée au corrigé étudiant."
    )
    suggestions = suggest_first_lab_rubric(analysis)
    by_criterion = {
        item.decision.criterion_id: item for item in suggestions
    }
    decisions = []
    for criterion in profile.criteria:
        suggestion = by_criterion[criterion.criterion_id]
        levels = tuple(RubricLevel)
        level = st.selectbox(
            criterion.label,
            options=levels,
            index=levels.index(suggestion.decision.level),
            format_func=lambda value: _RUBRIC_LEVEL_LABELS[value],
            help=criterion.description,
            key=f"grading-{profile.profile_id}-{source_id}-{criterion.criterion_id}",
        )
        decisions.append(RubricDecision(criterion.criterion_id, level))
        st.caption(f"Suggestion TPStudio : {suggestion.rationale}")
    proposal = build_formative_grade_proposal(profile, tuple(decisions))
    st.metric("Note proposée", f"{proposal.proposed_score}/20")
    st.caption(
        f"Base : {proposal.base_score}/20 · Bonus : +{proposal.bonus} · "
        f"Retraits : −{proposal.deduction}"
    )


def _build_semantic_provider(enabled: bool, *, environ=None):
    """Build a provider only from an explicit Analyze action."""
    if not enabled:
        return None
    environment = os.environ if environ is None else environ
    if not str(environment.get("OPENAI_API_KEY", "")).strip():
        return None
    return OpenAISemanticAnalysisProvider(model=_semantic_model())


def web_error_message(exc: BaseException) -> str:
    text = str(exc)
    safe_messages = {
        "Aucune copie sélectionnée.",
        "Le nom du fichier contient un chemin interdit.",
        "Seuls les fichiers .ipynb sont acceptés.",
        "source_id web invalide.",
        "Notebook invalide.",
        "Le dossier de sortie est vide.",
        "Le dossier de sortie est invalide.",
    }
    if isinstance(exc, ValueError) and text in safe_messages:
        return text
    return "Impossible de préparer le lot."


def _graph_detail_label(source_id: str, regression_index: int) -> str:
    """Return a readable, deterministic popover label unique across copies."""
    suffix = source_id[-8:] or "copie"
    return f"Détails {regression_index} · {suffix}"


def _render_interpretation_review(st, batch_result, output_dir: Path, copy_labels=None) -> None:
    try:
        only_pending = st.checkbox(
            "Seulement les cas à revoir", value=True, key=REVIEW_FILTER_KEY,
        )
        items = select_interpretation_review_items(
            batch_result, output_dir, only_pending=only_pending, copy_labels=copy_labels,
        )
    except (OSError, TypeError, ValueError) as exc:
        st.warning("Les décisions de revue ne peuvent pas être chargées.")
        return
    message = st.session_state.get(REVIEW_MESSAGE_KEY)
    if message:
        st.success(message)
        st.session_state[REVIEW_MESSAGE_KEY] = None
    if not items:
        st.info("Aucune interprétation ne nécessite actuellement une revue humaine.")
        return
    index = max(0, min(st.session_state.get(REVIEW_INDEX_KEY, 0), len(items) - 1))
    st.session_state[REVIEW_INDEX_KEY] = index
    previous, current, following = st.columns(3)
    with previous:
        if st.button("Précédent", disabled=index == 0, key="review-previous"):
            st.session_state[REVIEW_INDEX_KEY] = index - 1
            st.rerun()
    with current:
        st.caption(f"Interprétation {index + 1} / {len(items)}")
    with following:
        if st.button("Suivant", disabled=index == len(items) - 1, key="review-next"):
            st.session_state[REVIEW_INDEX_KEY] = index + 1
            st.rerun()
    item = items[index]
    trace = item.trace
    st.write(f"Copie : {item.copy_label}")
    st.write(f"Identifiant : {trace.expectation_id}")
    if item.stale_review:
        st.warning("Une revue précédente existe pour une autre version de cette copie.")
    st.markdown("**Consigne locale**")
    st.markdown(trace.local_context.local_prompt or "—")
    st.markdown("**Contexte scientifique**")
    context = "\n\n".join(trace.local_context.local_scientific_context)
    if trace.local_context.linked_protocol:
        context = "\n\n".join(filter(None, (context, trace.local_context.linked_protocol)))
    st.markdown(context or "—")
    st.markdown("**Réponse étudiante**")
    st.markdown(trace.student_answer or "—")
    st.markdown(f"**Proposition TPStudio :** {item.proposed_label}")
    st.markdown(f"**Feedback TPStudio :** {trace.tpstudio_feedback or '—'}")
    decision, feedback = review_prefill(item)
    labels = {
        InterpretationClassification.CLEARLY_SUFFICIENT: "CLEARLY_SUFFICIENT",
        InterpretationClassification.CLEARLY_INSUFFICIENT: "CLEARLY_INSUFFICIENT",
        InterpretationClassification.AMBIGUOUS: "AMBIGUOUS",
    }
    options = tuple(labels)
    selected = st.radio(
        "Décision enseignant", options,
        index=options.index(decision), format_func=labels.get,
        key=f"review-decision-{item.key}",
    )
    teacher_feedback = st.text_area(
        "Feedback enseignant", value=feedback,
        key=f"review-feedback-{item.key}",
    )
    if st.button("Enregistrer la décision", key=f"review-save-{item.key}"):
        reviewed = replace(
            trace,
            teacher_decision=selected,
            teacher_feedback=teacher_feedback,
            reviewed_at=datetime.now(timezone.utc).isoformat(),
        )
        try:
            append_interpretation_review(review_store_path(output_dir), reviewed)
        except (OSError, TypeError, ValueError):
            st.error("La décision n'a pas pu être enregistrée.")
        else:
            st.session_state[REVIEW_MESSAGE_KEY] = "Décision enregistrée."
            st.rerun()


def _render_review_corpus(st, batch_result, output_dir: Path) -> None:
    """Offer an explicit, pseudonymized download of human decisions."""
    try:
        history = load_interpretation_reviews(review_store_path(output_dir))
        pseudonym_key = load_or_create_corpus_pseudonym_key()
        current = tuple(
            trace
            for copy_result in batch_result.results
            for trace in copy_result.interpretation_review_traces
        )
        rows = build_interpretation_review_corpus(history, pseudonym_key=pseudonym_key, current_traces=current)
    except (OSError, TypeError, ValueError):
        st.warning("Le corpus de revues ne peut pas être préparé.")
        return
    stats = summarize_interpretation_review_corpus(rows)
    st.subheader("Corpus de revues")
    st.write(f"Historique des revues humaines : {stats['total']} décisions")
    if not rows:
        st.info("Aucune décision humaine à exporter.")
        return
    st.caption(
        "Le corpus ne contient pas les identifiants directs du roster (nom, email, etc.). "
        "Les copies et cellules reçoivent des pseudonymes locaux stables. "
        "Les textes libres peuvent toutefois contenir des noms saisis manuellement."
    )
    st.caption(
        f"Confirmées : {stats['confirmed']} · Remplacées : {stats['replaced']} · "
        f"Accords : {stats['agreement']} · Désaccords : {stats['disagreement']}"
    )
    st.download_button(
        "Exporter le corpus pseudonymisé",
        data=interpretation_review_corpus_jsonl(rows).encode("utf-8"),
        file_name="tpstudio-interpretation-reviews-a73c2d.jsonl",
        mime="application/x-ndjson",
        key="export-interpretation-review-corpus",
    )


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="TPStudio", page_icon=None, layout="wide")
    initialize_session_state(st.session_state)
    if st.session_state[WORKSPACE_KEY] is None:
        st.session_state[WORKSPACE_KEY] = WebWorkspace()
    workspace = st.session_state[WORKSPACE_KEY]

    st.title("TPStudio")
    st.subheader("Correction assistée de travaux pratiques")
    st.info("Mode : détection automatique du TP par copie")
    with st.sidebar:
        st.header("Options")
        st.caption("Les options d’export seront disponibles après la phase d’analyse.")
        semantic_enabled = st.checkbox(
            "Activer l’analyse sémantique (API OpenAI)",
            value=False,
            key=SEMANTIC_ANALYSIS_ENABLED_KEY,
        )
        semantic_model = _semantic_model()
        if semantic_enabled:
            st.caption(f"Modèle sémantique : {semantic_model}")
        try:
            roster = load_roster()
            st.caption(f"Étudiants : {len(roster)} chargés")
        except ValueError:
            roster = ()
            st.warning("Le roster local est invalide.")
        roster_upload = st.file_uploader(
            "Importer une liste d'étudiants", type=["csv"], key="tpstudio_roster_upload",
        )
        if roster_upload is not None and st.button("Importer / mettre à jour la liste", key="tpstudio_roster_save"):
            try:
                imported_roster = parse_roster_csv(roster_upload.getvalue().decode("utf-8-sig"))
                save_roster(imported_roster, default_roster_path())
                st.success(f"Roster enregistré : {len(imported_roster)} étudiants.")
                st.rerun()
            except (UnicodeDecodeError, TypeError, ValueError, OSError):
                st.error("Le fichier roster n'a pas pu être importé.")
    generation = st.session_state[UPLOADER_GENERATION_KEY]
    uploads = st.file_uploader("Sélectionner les notebooks (.ipynb)", type=["ipynb"], accept_multiple_files=True, key=f"tpstudio_web_uploads_{generation}")
    # A75a5.1 is analysis-only.  Keep historical planning inputs internal until
    # the export phase is introduced, so no artifact naming is suggested here.
    output_dir = default_output_dir()
    options = WebBatchOptions()
    copies = []
    if uploads:
        try:
            payload = tuple((upload.name, upload.getvalue()) for upload in uploads)
            previous = {
                item.source_id: item
                for item in st.session_state.get(SELECTION_KEY, ())
                if item.identity is not None and item.identity.source.value == "manual"
            }
            copies = []
            for item in workspace.replace_selection(payload):
                identified = identify_selected_copy(item)
                prior = previous.get(item.source_id)
                if prior is not None and prior.content_sha256 == item.content_sha256:
                    identified = replace(identified, identity=prior.identity)
                copies.append(identified)
            st.session_state[SELECTION_KEY] = tuple(copies)
        except (TypeError, ValueError) as exc:
            st.error(web_error_message(exc))
            reset_web_session(st.session_state)
            copies = []
    else:
        copies = []
        workspace.reset()
        if st.session_state.get(SELECTION_KEY) or st.session_state.get(PLAN_KEY) is not None:
            reset_web_session(st.session_state)
        else:
            st.session_state[SELECTION_KEY] = ()
            clear_prepared_batch(st.session_state)
    signature = _input_signature(copies, output_dir, options) if copies and all(item.workspace_path.exists() for item in copies) else ()
    invalidate_if_signature_changed(st.session_state, signature)
    if st.button("Vérifier le lot", type="primary"):
        try:
            plan = build_batch_plan_from_web_selection(tuple(copies), output_dir, options)
            set_prepared_batch(st.session_state, plan, signature)
            st.success("Lot prêt")
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            clear_prepared_batch(st.session_state)
            st.error(web_error_message(exc))
    if st.session_state.get(PLAN_KEY) is not None and st.session_state.get(SIGNATURE_KEY) == signature:
        plan = st.session_state[PLAN_KEY]
        st.success("Lot prêt")
        st.write(f"Copies : {len(plan.sources)}")
        identity_by_id = {item.source_id: item.identity for item in copies}
        table_rows = []
        for row in batch_plan_rows(plan, identity_by_id):
            table_rows.append({
                "Copie": row.copy_label,
                "Fichier déposé": row.original_filename,
                "Étudiants détectés": row.students_display,
                "Statut identité": row.identity_status,
                "Source": row.identity_source,
            })
        st.table(table_rows)
        unresolved = [item for item in copies if item.identity and item.identity.status is CopyIdentityStatus.TO_REVIEW]
        if unresolved:
            st.markdown("### Résolution des identités")
            roster_candidates = identity_resolution_candidates(copies, roster)
            roster_by_name = {student.display_name: student for student in roster_candidates}
            options_names = tuple(roster_by_name)
            for item in unresolved:
                identity = item.identity
                st.markdown(f"**Fichier :** {item.original_filename}")
                if roster:
                    suggested = suggest_roster_students(item.original_filename, roster)
                    detected = tuple(student.to_identity().display_name for student in suggested)
                else:
                    detected = tuple(student.display_name for student in identity.students if student.display_name in roster_by_name)
                if not options_names:
                    st.warning("Aucun étudiant connu n'est disponible pour cette copie.")
                    continue
                chosen_names = st.multiselect(
                    "Étudiants",
                    options_names,
                    default=detected,
                    key=f"identity-choice-{item.source_id}",
                )
                if st.button("Confirmer l'identité", key=f"identity-confirm-{item.source_id}"):
                    try:
                        selected = confirm_copy_identity(
                            item, tuple(roster_by_name[name] for name in chosen_names),
                        )
                        updated = tuple(
                            selected if current.source_id == item.source_id else current
                            for current in copies
                        )
                        new_signature = _input_signature(updated, output_dir, options)
                        new_plan = build_batch_plan_from_web_selection(updated, output_dir, options)
                        st.session_state[SELECTION_KEY] = updated
                        set_prepared_batch(st.session_state, new_plan, new_signature)
                        st.session_state[REVIEW_INDEX_KEY] = 0
                        st.success("Identité confirmée.")
                        st.rerun()
                    except (TypeError, ValueError, FileNotFoundError, OSError) as exc:
                        st.error(web_error_message(exc))
        can_run, reasons = can_run_batch(copies, plan)
        if not can_run:
            st.warning("Certaines identités doivent être vérifiées avant correction.")
        if st.button("Analyser", type="primary", disabled=not can_run or st.session_state[RUN_IN_PROGRESS_KEY]):
            st.session_state[RUN_IN_PROGRESS_KEY] = True
            try:
                provider = _build_semantic_provider(semantic_enabled)
                if semantic_enabled and provider is None:
                    clear_dispatch_result(st.session_state)
                    st.warning(
                        "Analyse sémantique activée, mais OPENAI_API_KEY est absente. "
                        "Le lot n’a pas été analysé."
                    )
                else:
                    with st.spinner("Analyse du lot en cours…"):
                        if provider is None:
                            result = run_selected_dispatch(copies)
                        else:
                            result = run_selected_dispatch(copies, semantic_provider=provider)
                    set_dispatch_result(
                        st.session_state,
                        result,
                        _analysis_signature(signature, semantic_enabled, semantic_model),
                    )
                clear_run_result(st.session_state)
                st.session_state[REVIEW_INDEX_KEY] = 0
            except Exception:
                clear_dispatch_result(st.session_state)
                st.error("Impossible d'analyser le lot.")
            finally:
                st.session_state[RUN_IN_PROGRESS_KEY] = False
        current_analysis_signature = _analysis_signature(signature, semantic_enabled, semantic_model)
        invalidate_dispatch_if_signature_changed(st.session_state, current_analysis_signature)
        dispatch_result = get_current_dispatch_result(st.session_state, current_analysis_signature)
        if dispatch_result is not None:
            st.subheader("Résultat de l'analyse")
            st.write(
                f"Copies : {len(dispatch_result.copies)} · "
                f"Analysées : {dispatch_result.analyzed_count} · "
                f"Reconnues — correction indisponible : {dispatch_result.resolved_not_ready_count} · "
                f"À confirmer : {dispatch_result.unresolved_count} · "
                f"Erreurs : {dispatch_result.error_count} · "
                f"Non traitées : {dispatch_result.skipped_count}"
            )
            overrides = get_project_overrides(st.session_state)
            rows = batch_dispatch_rows(dispatch_result, copies, overrides)
            export_results = get_export_results(st.session_state)
            for row, item in zip(rows, dispatch_result.copies):
                icon = {
                    "Analysée": "✅", "TP à confirmer": "⚠️", "Aucun TP reconnu": "⚠️",
                    "Erreur technique": "❌", "Non traitée": "⏭️",
                    "Non analysée à cause d'une erreur précédente": "⏭️",
                }.get(row.status, "ℹ️")
                with st.expander(f"{icon} {row.display_name} — {row.status}", expanded=True):
                    if row.project_title:
                        st.write(f"TP : {row.project_title}")
                    if row.confidence:
                        st.write(f"Confiance : {row.confidence}")
                    st.write(f"Provenance : {row.provenance}")
                    if row.validated_by_teacher:
                        st.write("✓ Validé par l'enseignant")
                    if row.error_message:
                        st.warning(row.error_message)
                    if item.status is BatchCopyDispatchStatus.RESOLVED_NOT_READY:
                        st.info(
                            "TP reconnu. La correction automatique complète de ce TP "
                            "n’est pas encore disponible."
                        )
                    semantic_rows = semantic_response_rows(
                        item.dispatch.semantic_response_analyses if item.dispatch else (),
                        source_id=item.source_id,
                    )
                    if semantic_rows:
                        st.markdown("### Analyse des réponses scientifiques")
                        st.caption(
                            "Aperçu sémantique partiel : les résultats sont soumis à la validation du professeur "
                            "et ne constituent ni une note ni une correction complète."
                        )
                        for semantic_row in semantic_rows:
                            with st.container(border=True):
                                st.markdown(
                                    f"**{semantic_row.production_id}** · {semantic_row.role_label} · "
                                    f"{semantic_row.binding_label}"
                                )
                                st.text_area(
                                    "Réponse étudiante",
                                    value=semantic_row.student_response or "",
                                    height=100,
                                    disabled=True,
                                    key=f"{semantic_row.stable_key}-response",
                                )
                                for criterion in semantic_row.criteria:
                                    st.markdown(
                                        f"**{criterion.description}** · {criterion.status_label} · "
                                        f"{criterion.importance_label}"
                                    )
                                    st.caption(f"Critère : {criterion.criterion_id}")
                                    if criterion.evidence:
                                        st.caption(f"Preuve : {criterion.evidence}")
                                if semantic_row.contradictions:
                                    st.warning(
                                        "Contradictions à examiner par le professeur : "
                                        + " ; ".join(semantic_row.contradictions)
                                    )
                                if semantic_row.confidence:
                                    st.caption(f"Confiance déclarée : {semantic_row.confidence}")
                                for diagnostic in semantic_row.diagnostics:
                                    st.info(diagnostic)
                    if row.evidence:
                        st.markdown("**Détails de la détection**")
                        with st.container():
                            for kind, text in row.evidence:
                                st.caption(f"{kind} : {text}")
                    active_analysis = active_analysis_for_source(dispatch_result, overrides, item.source_id)
                    if active_analysis is not None:
                        from tpstudio.reporting import build_teacher_copy_report
                        report = build_teacher_copy_report(active_analysis)
                        st.markdown("**Contrôle scientifique**")
                        overview = build_teacher_scientific_overview(report)
                        for overview_row in overview.rows:
                            st.markdown(
                                f"{scientific_severity_icon(overview_row.severity)} "
                                f"**{overview_row.label}** — {overview_row.summary}"
                            )
                            if overview_row.details:
                                details_key = scientific_detail_widget_key(item.source_id, overview_row.key)
                                if st.checkbox(
                                    f"Afficher les détails — {overview_row.label}",
                                    key=details_key,
                                ):
                                    with st.container():
                                        for detail in overview_row.details:
                                            st.caption(detail)
                        graph_rows = graph_summary_rows(report, key_prefix=item.source_id)
                        for graph_row in graph_rows:
                            st.markdown(f"{graph_row.icon} **{graph_row.headline}**")
                            for line in graph_row.summary_lines:
                                st.caption(line)
                        _render_first_lab_grading(st, active_analysis, item.source_id)
                    export_state = export_results.get(item.source_id)
                    if export_state is not None:
                        if export_state.result is not None:
                            st.success("Export réussi")
                            st.markdown("**Artefacts**")
                            st.caption(f"Notebook corrigé : {export_state.result.notebook_artifact.path}")
                            st.caption(f"Version HTML : {export_state.result.html_artifact.path}")
                        else:
                            st.error("❌ Erreur d'export")
                            st.caption(export_state.error_message)
                    if item.status.value == "unresolved" or active_analysis is not None:
                        current_project = active_analysis.project_id if active_analysis is not None else None
                        if active_analysis is not None and not row.validated_by_teacher:
                            edit = st.checkbox("Modifier le TP", key=f"edit-project-{item.source_id}")
                        else:
                            edit = True
                        if edit:
                            choices = project_choices_for_source(dispatch_result, item.source_id)
                            if current_project in choices:
                                default_index = choices.index(current_project)
                            else:
                                default_index = 0
                            chosen = st.selectbox(
                                "TP à utiliser",
                                choices,
                                index=default_index,
                                format_func=lambda value: project_descriptor(value).title,
                                key=f"project-choice-{item.source_id}",
                            )
                            if st.button("Utiliser ce TP", key=f"use-project-{item.source_id}"):
                                try:
                                    source = active_analysis.source if active_analysis is not None else next(
                                        request.source for request in build_dispatch_requests_from_web_selection(tuple(copies))
                                        if request.source_id == item.source_id
                                    )
                                    provider = _build_semantic_provider(semantic_enabled)
                                    if semantic_enabled and provider is None:
                                        st.warning(
                                            "Analyse sémantique activée, mais OPENAI_API_KEY est absente."
                                        )
                                        continue
                                    if provider is None:
                                        explicit_dispatch = analyze_selected_copy(source, chosen)
                                    else:
                                        explicit_dispatch = analyze_selected_copy(
                                            source, chosen, semantic_provider=provider,
                                        )
                                    if explicit_dispatch.analysis is None:
                                        raise ValueError("Le projet choisi n'a pas permis d'analyser cette copie.")
                                    set_project_override(st.session_state, WebCopyOverride(
                                        item.source_id, chosen, explicit_dispatch.analysis,
                                    ))
                                    st.rerun()
                                except Exception:
                                    st.error("Impossible d'analyser la copie avec ce TP.")
                        if row.validated_by_teacher and st.button("Revenir à la détection automatique", key=f"auto-project-{item.source_id}"):
                            remove_project_override(st.session_state, item.source_id)
                            st.rerun()
            st.markdown("### Options d'export")
            export_output_text = st.text_input(
                "Dossier des corrections",
                value=str(default_output_dir()),
                key="tpstudio_export_output_dir",
            )
            include_teacher_feedback = st.checkbox("Inclure le retour professeur", key="export-teacher-feedback")
            include_diagnostics = st.checkbox("Inclure les diagnostics", key="export-diagnostics")
            include_limitations = st.checkbox("Inclure les limitations", key="export-limitations")
            hide_code = st.checkbox("Masquer le code dans le HTML", key="export-hide-code")
            hide_outputs = st.checkbox("Masquer les sorties dans le HTML", key="export-hide-outputs")
            embed_images = st.checkbox("Inclure les images", value=True, key="export-embed-images")
            include_input_prompts = st.checkbox("Inclure les invites d'entrée", key="export-input-prompts")
            include_output_prompts = st.checkbox("Inclure les invites de sortie", key="export-output-prompts")
            overwrite = st.checkbox("Autoriser le remplacement des fichiers existants", key="export-overwrite")
            ready_count = exportable_count(dispatch_result, overrides)
            st.write(
                f"Copies prêtes à exporter : {ready_count} · "
                f"Copies sans analyse active : {non_exportable_count(dispatch_result, overrides)} "
                f"(dont {dispatch_result.resolved_not_ready_count} reconnue(s) sans couverture)"
            )
            if st.button("Exporter les copies analysées", disabled=ready_count == 0, key="export-active-copies"):
                try:
                    output_dir = resolve_output_dir(export_output_text)
                    export_options = CopyExportOptions(
                        overwrite=overwrite,
                        include_teacher_feedback=include_teacher_feedback,
                        include_diagnostics=include_diagnostics,
                        include_limitations=include_limitations,
                        embed_images=embed_images,
                        include_code=not hide_code,
                        include_outputs=not hide_outputs,
                        include_input_prompts=include_input_prompts,
                        include_output_prompts=include_output_prompts,
                    )
                    set_export_results(
                        st.session_state,
                        export_active_copies(
                            dispatch_result,
                            overrides,
                            output_dir=output_dir,
                            options=export_options,
                            selected_copies=copies,
                        ),
                    )
                    st.rerun()
                except (TypeError, ValueError, OSError) as exc:
                    st.error(web_error_message(exc))
    if st.button("Réinitialiser"):
        workspace.reset()
        reset_web_session(st.session_state)
        st.rerun()


if __name__ == "__main__":
    main()
