"""A72a local Streamlit application: prepare, never run, a batch."""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from datetime import datetime, timezone

from tpstudio.batch import BatchCopyStatus, render_batch_report_markdown
from tpstudio.web.execution import can_run_batch, run_prepared_batch
from tpstudio.web.model import WebBatchOptions
from tpstudio.web.identity import identify_selected_copy
from tpstudio.web.planning import WebInputError, build_batch_plan_from_web_selection, resolve_output_dir
from tpstudio.web.presenters import batch_plan_rows, has_output_name_collision
from tpstudio.web.presenters import review_prefill, select_interpretation_review_items
from tpstudio.interpretation import InterpretationClassification
from tpstudio.review_store import append_interpretation_review, review_store_path
from tpstudio.web.state import (
    PLAN_KEY, SELECTION_KEY, SIGNATURE_KEY, WORKSPACE_KEY,
    UPLOADER_GENERATION_KEY, clear_prepared_batch, initialize_session_state,
    invalidate_if_signature_changed, reset_web_session, set_prepared_batch,
    clear_run_result, get_current_run_result, set_run_result, RUN_IN_PROGRESS_KEY,
    default_output_dir,
    REVIEW_FILTER_KEY, REVIEW_INDEX_KEY, REVIEW_MESSAGE_KEY,
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


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="TPStudio", page_icon=None, layout="wide")
    initialize_session_state(st.session_state)
    if st.session_state[WORKSPACE_KEY] is None:
        st.session_state[WORKSPACE_KEY] = WebWorkspace()
    workspace = st.session_state[WORKSPACE_KEY]

    st.title("TPStudio")
    st.subheader("Correction assistée de travaux pratiques")
    st.info("TP actif : Snell-Descartes · Projet : snells-laws-mvp")
    with st.sidebar:
        st.header("Options")
        include_teacher = st.checkbox("Inclure le retour professeur")
        include_diagnostics = st.checkbox("Inclure les diagnostics")
        hide_code = st.checkbox("Masquer le code dans le HTML")
        hide_outputs = st.checkbox("Masquer les sorties dans le HTML")
        overwrite = st.checkbox("Autoriser le remplacement des fichiers existants")
    generation = st.session_state[UPLOADER_GENERATION_KEY]
    uploads = st.file_uploader("Sélectionner les notebooks (.ipynb)", type=["ipynb"], accept_multiple_files=True, key=f"tpstudio_web_uploads_{generation}")
    output_text = st.text_input("Dossier des corrections", value=str(default_output_dir()))
    copies = []
    if uploads:
        try:
            payload = tuple((upload.name, upload.getvalue()) for upload in uploads)
            copies = [identify_selected_copy(item) for item in workspace.replace_selection(payload)]
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
    output_error = None
    try:
        output_dir = resolve_output_dir(output_text)
    except WebInputError as exc:
        output_dir = Path(output_text)
        output_error = exc
    options = WebBatchOptions(include_teacher, include_diagnostics, hide_code, hide_outputs, overwrite)
    signature = _input_signature(copies, output_dir, options) if copies and all(item.workspace_path.exists() for item in copies) else ()
    invalidate_if_signature_changed(st.session_state, signature)
    if st.button("Vérifier le lot", type="primary"):
        if output_error is not None:
            st.error(web_error_message(output_error))
        else:
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
        st.write(f"Copies : {len(plan.sources)} · Dossier de sortie : {plan.output_dir}")
        st.write(f"Retour professeur : {'oui' if options.include_teacher_feedback else 'non'} · Diagnostics : {'oui' if options.include_diagnostics else 'non'}")
        st.write(f"Code HTML : {'masqué' if options.hide_code else 'visible'} · Sorties HTML : {'masquées' if options.hide_outputs else 'visibles'} · Remplacement : {'oui' if options.overwrite else 'non'}")
        identity_by_id = {item.source_id: item.identity for item in copies}
        table_rows = []
        for row in batch_plan_rows(plan, identity_by_id):
            table_rows.append({
                "Copie": row.copy_label,
                "Fichier déposé": row.original_filename,
                "Étudiants détectés": row.students_display,
                "Statut identité": row.identity_status,
                "Source": row.identity_source,
                "Notebook corrigé": row.notebook_output_name,
                "Version HTML": row.html_output_name,
            })
        st.table(table_rows)
        if has_output_name_collision(plan):
            st.info("Des noms de fichiers identiques ont été détectés. TPStudio a préparé des noms de sortie distincts.")
        can_run, reasons = can_run_batch(copies, plan)
        if not can_run:
            st.warning("Certaines identités doivent être vérifiées avant correction.")
        if options.overwrite:
            st.warning("Les fichiers de sortie existants pourront être remplacés.")
        if st.button("Corriger le lot", type="primary", disabled=not can_run or st.session_state[RUN_IN_PROGRESS_KEY]):
            st.session_state[RUN_IN_PROGRESS_KEY] = True
            try:
                plan.output_dir.mkdir(parents=True, exist_ok=True)
                if not plan.output_dir.is_dir():
                    raise ValueError("Le dossier de sortie est invalide.")
                with st.spinner("Correction du lot en cours…"):
                    result = run_prepared_batch(plan)
                set_run_result(st.session_state, result, signature)
                st.session_state[REVIEW_INDEX_KEY] = 0
            except Exception:
                clear_run_result(st.session_state)
                st.error("Impossible de lancer la correction du lot.")
            finally:
                st.session_state[RUN_IN_PROGRESS_KEY] = False
        result = get_current_run_result(st.session_state, signature)
        if result is not None:
            if result.success:
                st.success("Correction terminée.")
            elif result.success_count:
                st.warning("Le lot a été traité avec des erreurs.")
            else:
                st.warning("Aucune copie n'a été corrigée.")
            st.subheader("Résultat de la correction")
            st.write(f"Copies : {len(result.results)} · Réussies : {result.success_count} · Échecs : {result.failed_count} · Ignorées : {result.skipped_count} · Annotations : {result.total_annotation_count} · Revue humaine confirmée : {result.human_review_count}")
            from tpstudio.web.presenters import artifact_download_info, batch_run_rows
            result_rows = batch_run_rows(result, copies)
            st.table([{
                "Copie": row.copy_label, "Étudiants": row.students_display,
                "Statut": row.status, "Notebook corrigé": row.notebook_output_name,
                "Version HTML": row.html_output_name, "Annotations": row.annotation_count,
                "Revue humaine": row.human_review, "Limites": row.limitations,
                "Problème": row.problem,
            } for row in result_rows])
            for item, row in zip(result.results, result_rows):
                if item.status is BatchCopyStatus.SUCCESS:
                    with st.expander(f"{row.copy_label} · {row.students_display}"):
                        for kind, label in (("notebook", "Télécharger le notebook"), ("html", "Télécharger le HTML")):
                            try:
                                filename, mime, path = artifact_download_info(item, plan.output_dir, kind)
                                st.download_button(label, data=path.read_bytes(), file_name=filename, mime=mime, key=f"download-{item.source_id}-{kind}")
                            except (FileNotFoundError, ValueError):
                                st.warning("Artefact indisponible.")
            with st.expander("Rapport du lot"):
                st.markdown(render_batch_report_markdown(result))
            if any(item.interpretation_review_traces for item in result.results):
                st.subheader("Revue humaine des interprétations")
                review_labels = {}
                for selected in copies:
                    students = " · ".join(student.display_name for student in getattr(selected.identity, "students", ()))
                    review_labels[selected.source_id] = f"{selected.original_filename} · {students or '—'}"
                _render_interpretation_review(st, result, plan.output_dir, review_labels)
    if st.button("Réinitialiser"):
        workspace.reset()
        reset_web_session(st.session_state)
        st.rerun()


if __name__ == "__main__":
    main()
