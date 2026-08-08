"""A72a local Streamlit application: prepare, never run, a batch."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from tpstudio.web.model import WebBatchOptions
from tpstudio.web.identity import identify_selected_copy
from tpstudio.web.planning import WebInputError, build_batch_plan_from_web_selection
from tpstudio.web.presenters import batch_plan_rows, has_output_name_collision
from tpstudio.web.state import (
    PLAN_KEY, SELECTION_KEY, SIGNATURE_KEY, WORKSPACE_KEY,
    UPLOADER_GENERATION_KEY, clear_prepared_batch, initialize_session_state,
    invalidate_if_signature_changed, reset_web_session, set_prepared_batch,
)
from tpstudio.web.workspace import WebWorkspace


def _input_signature(copies, output_dir: Path, options: WebBatchOptions) -> tuple:
    return tuple((item.source_id, item.original_filename, item.content_sha256) for item in copies), str(output_dir), options


def web_error_message(exc: BaseException) -> str:
    text = str(exc)
    safe_messages = {
        "Aucune copie sélectionnée.",
        "Le nom du fichier contient un chemin interdit.",
        "Seuls les fichiers .ipynb sont acceptés.",
        "source_id web invalide.",
        "Notebook invalide.",
    }
    if isinstance(exc, ValueError) and text in safe_messages:
        return text
    return "Impossible de préparer le lot."


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
    output_text = st.text_input("Dossier de sortie", value="./tpstudio-output")
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
    try:
        output_dir = Path(output_text).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        output_dir = Path(output_text)
    options = WebBatchOptions(include_teacher, include_diagnostics, hide_code, hide_outputs, overwrite)
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
        st.info("Le lancement de la correction sera ajouté au prochain jalon.")
    if st.button("Réinitialiser"):
        workspace.reset()
        reset_web_session(st.session_state)
        st.rerun()


if __name__ == "__main__":
    main()
