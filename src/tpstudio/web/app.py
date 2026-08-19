"""A72a local Streamlit application: prepare, never run, a batch."""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from datetime import datetime, timezone

from tpstudio.batch import BatchCopyStatus, render_batch_report_markdown
from tpstudio.web.execution import analyze_selected_copy, can_run_batch, run_selected_dispatch
from tpstudio.web.model import WebBatchOptions
from tpstudio.web.identity import (
    CopyIdentityStatus, StudentIdentity, confirm_copy_identity,
    identify_selected_copy,
)
from tpstudio.web.model import WebCopyOverride
from tpstudio.web.planning import WebInputError, build_batch_plan_from_web_selection, build_dispatch_requests_from_web_selection
from tpstudio.projects import project_descriptor
from tpstudio.web.presenters import (
    batch_plan_rows, graph_summary_rows,
    identity_resolution_candidates, active_analysis_for_source, batch_dispatch_rows,
    project_choices_for_source,
)
from tpstudio.web.roster import (
    default_roster_path, load_roster, parse_roster_csv, save_roster,
    suggest_roster_students,
)
from tpstudio.web.presenters import review_prefill, select_interpretation_review_items
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
    get_project_overrides, set_project_override, remove_project_override,
)
from tpstudio.web.workspace import WebWorkspace


def _input_signature(copies, output_dir: Path, options: WebBatchOptions) -> tuple:
    return tuple((item.source_id, item.original_filename, item.content_sha256,
                  getattr(getattr(item, "identity", None), "status", None),
                  tuple(getattr(getattr(item, "identity", None), "students", ()))) for item in copies), str(output_dir), options


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
                with st.spinner("Analyse du lot en cours…"):
                    result = run_selected_dispatch(copies)
                set_dispatch_result(st.session_state, result, signature)
                clear_run_result(st.session_state)
                st.session_state[REVIEW_INDEX_KEY] = 0
            except Exception:
                clear_dispatch_result(st.session_state)
                st.error("Impossible d'analyser le lot.")
            finally:
                st.session_state[RUN_IN_PROGRESS_KEY] = False
        dispatch_result = get_current_dispatch_result(st.session_state, signature)
        if dispatch_result is not None:
            st.subheader("Résultat de l'analyse")
            st.write(f"Copies : {len(dispatch_result.copies)} · Analysées : {dispatch_result.analyzed_count} · À confirmer : {dispatch_result.unresolved_count} · Erreurs : {dispatch_result.error_count} · Non traitées : {dispatch_result.skipped_count}")
            overrides = get_project_overrides(st.session_state)
            rows = batch_dispatch_rows(dispatch_result, copies, overrides)
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
                    if row.evidence:
                        st.markdown("**Détails de la détection**")
                        with st.container():
                            for kind, text in row.evidence:
                                st.caption(f"{kind} : {text}")
                    active_analysis = active_analysis_for_source(dispatch_result, overrides, item.source_id)
                    if active_analysis is not None:
                        from tpstudio.reporting import build_teacher_copy_report
                        graph_rows = graph_summary_rows(build_teacher_copy_report(active_analysis), key_prefix=item.source_id)
                        for graph_row in graph_rows:
                            st.markdown(f"{graph_row.icon} **{graph_row.headline}**")
                            for line in graph_row.summary_lines:
                                st.caption(line)
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
                                    explicit_dispatch = analyze_selected_copy(source, chosen)
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
    if st.button("Réinitialiser"):
        workspace.reset()
        reset_web_session(st.session_state)
        st.rerun()


if __name__ == "__main__":
    main()
