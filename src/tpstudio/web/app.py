"""A72a local Streamlit application: prepare, never run, a batch."""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import os
import webbrowser

from tpstudio.batch import BatchCopyStatus, render_batch_report_markdown
from tpstudio.export import CopyExportOptions
from tpstudio.export import render_analyzed_copy_html
from tpstudio.annotation import (
    AnnotationReview, AnnotationReviewAction, AnnotationReviewLevel,
    build_annotation_plan,
)
from tpstudio.orchestration import BatchCopyDispatchStatus
from tpstudio.semantic_analysis import (
    CachedSemanticAnalysisProvider,
    DEFAULT_OPENAI_SEMANTIC_MODEL,
    OpenAISemanticAnalysisProvider,
    SemanticRole,
)
from tpstudio.web.execution import (
    analyze_selected_copy,
    can_run_batch,
    export_active_copies,
    regenerate_missing_graph_outputs,
    run_selected_dispatch,
    should_use_semantic_provider,
)
from tpstudio.web.model import WebBatchOptions
from tpstudio.web.mail_drafts import (
    load_sender_email,
    open_correction_mail_in_apple_mail,
    prepare_correction_mail_draft,
    save_sender_email,
)
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
    confirm_exact_roster_identity, default_roster_path, load_roster,
    enrich_identity_for_mail,
    parse_roster_csv, save_roster,
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
    get_annotation_reviews, set_annotation_review,
    set_annotation_reviews_for_source,
    get_html_preview, set_html_preview,
    SEMANTIC_ANALYSIS_ENABLED_KEY,
    REGENERATE_GRAPH_OUTPUTS_KEY,
)
from tpstudio.web.workspace import WebWorkspace
from tpstudio.web.annotation_review_cache import (
    load_annotation_reviews,
    load_shared_response_reviews,
    save_annotation_reviews,
    save_shared_response_reviews,
)


_ACTIVE_ANALYSIS_COPY_KEY = "active-analysis-copy"
_REVIEW_COPY_RESTORE_KEY = "tpstudio-review-copy-to-restore"
_MAIL_DRAFTS_KEY = "tpstudio-mail-drafts"


def _rerun_copy_review(st, source_id: str) -> None:
    """Rerun the UI while explicitly preserving the reviewed copy."""

    st.session_state[_REVIEW_COPY_RESTORE_KEY] = source_id
    st.rerun()


def _restore_reviewed_copy(state, valid_source_ids: tuple[str, ...]) -> None:
    """Restore a copy selected before an annotation-review rerun."""

    source_id = state.pop(_REVIEW_COPY_RESTORE_KEY, None)
    if source_id in valid_source_ids:
        state[_ACTIVE_ANALYSIS_COPY_KEY] = source_id


def _input_signature(copies, output_dir: Path, options: WebBatchOptions) -> tuple:
    return tuple((item.source_id, item.original_filename, item.content_sha256,
                  getattr(getattr(item, "identity", None), "status", None),
                  tuple(getattr(getattr(item, "identity", None), "students", ()))) for item in copies), str(output_dir), options


def _analysis_signature(
    input_signature: tuple,
    semantic_enabled: bool,
    model: str,
    include_semantic_references: bool = False,
    regenerate_graph_outputs: bool = False,
) -> tuple:
    """Signature for analysis results; planning remains independent of AI."""
    return (
        input_signature,
        bool(semantic_enabled),
        model,
        bool(include_semantic_references),
        bool(regenerate_graph_outputs),
    )


def _semantic_model() -> str:
    return os.getenv("TPSTUDIO_OPENAI_MODEL") or DEFAULT_OPENAI_SEMANTIC_MODEL


def _open_local_html_artifact(path, *, opener=None) -> bool:
    """Ask the local operating system to open one exported HTML artifact."""

    artifact = Path(path).resolve()
    if not artifact.is_file() or artifact.suffix.casefold() != ".html":
        return False
    open_in_browser = opener or webbrowser.open_new_tab
    return bool(open_in_browser(artifact.as_uri()))


_ANNOTATION_REVIEW_LABELS = {
    AnnotationReviewAction.KEEP: "Conserver",
    AnnotationReviewAction.EDIT: "Modifier",
    AnnotationReviewAction.REMOVE: "Retirer",
}

_ANNOTATION_LEVEL_LABELS = {
    AnnotationReviewLevel.ABSENT: "Absence de réponse",
    AnnotationReviewLevel.TO_REVIEW: "À revoir",
    AnnotationReviewLevel.PARTIAL: "Partiel",
    AnnotationReviewLevel.GOOD: "Bien",
    AnnotationReviewLevel.VERY_GOOD: "Très bien",
}

_SEVERITY_DEFAULT_REVIEW_LEVEL = {
    "blocking": AnnotationReviewLevel.ABSENT,
    "important": AnnotationReviewLevel.TO_REVIEW,
    "attention": AnnotationReviewLevel.PARTIAL,
    "info": AnnotationReviewLevel.VERY_GOOD,
}


def _annotation_review_signature(reviews) -> tuple:
    return tuple(sorted(
        (
            item.annotation_id,
            item.action.value,
            item.message,
            item.level.value if item.level is not None else None,
        )
        for item in reviews
    ))


def _grading_widget_key(source_id: str, criterion_id: str) -> str:
    profile = FIRST_LAB_FORMATIVE_GRADING_PROFILE
    return f"grading-{profile.profile_id}-{source_id}-{criterion_id}"


def _coerce_rubric_level(value, fallback: RubricLevel) -> RubricLevel:
    """Accept grading values left in Streamlit state by older UI versions."""

    if type(value) is RubricLevel:
        return value
    if type(value) is AnnotationReviewLevel:
        return RubricLevel[value.name]
    if isinstance(value, str):
        normalized = value.strip().casefold()
        by_text = {
            level.name.casefold(): level for level in RubricLevel
        } | {
            level.name.replace("_", " ").casefold(): level
            for level in RubricLevel
        } | {
            label.casefold(): level for level, label in _RUBRIC_LEVEL_LABELS.items()
        }
        return by_text.get(normalized, fallback)
    if type(value) is int:
        try:
            return RubricLevel(value)
        except ValueError:
            pass
    return fallback


def _annotation_grading_criterion(analysis, annotation) -> str | None:
    """Map a reviewed comment to the closest first-session rubric criterion."""

    if analysis.project_id != FIRST_LAB_FORMATIVE_GRADING_PROFILE.project_id:
        return None
    if annotation in tuple(build_annotation_plan(analysis).summary_annotations):
        return "completion"
    contracts = {
        item.production_id: item.semantic_role
        for item in analysis.project.semantic_response_expectations
    }
    role = contracts.get(getattr(annotation, "production_id", None))
    if getattr(annotation, "production_id", None) in {
        "dynamic_schematic", "static_schematic",
    }:
        return "protocols"
    if role is SemanticRole.OBJECTIVE:
        return "manipulation_objectives"
    if role is SemanticRole.PROTOCOL:
        return "protocols"
    if role in (SemanticRole.INTERPRETATION, SemanticRole.CONCLUSION):
        return "interpretation"
    return "results_presentation"


def _ordered_review_annotations(plan) -> tuple:
    """Match the review selector order to the rendered notebook order."""

    localized = tuple(sorted(
        plan.annotations,
        key=lambda item: item.target_cell_index,
    ))
    # Summary comments are rendered in a dedicated cell immediately after
    # the notebook heading, before every localized annotation.
    return tuple(plan.summary_annotations) + localized


def _focus_annotation_html(document: str, annotation_id: str | None) -> str:
    """Highlight and reveal one annotation inside the preview iframe."""

    if annotation_id is None:
        return document
    script = f"""
<script>
document.addEventListener("DOMContentLoaded", () => {{
  const target = document.getElementById({json.dumps(annotation_id)});
  if (target) {{
    target.classList.add("tpstudio-review-focus");
    requestAnimationFrame(() => target.scrollIntoView({{
      behavior: "smooth", block: "center", inline: "nearest"
    }}));
  }}
}});
</script>
"""
    return document.replace("</body>", script + "</body>", 1)


def _review_preview_component(
    document: str,
    selected_id: str | None,
    *,
    scroll_request: dict | None = None,
    key: str,
):
    """Render the clickable notebook preview and return its selected comment."""

    import streamlit.components.v1 as components

    component = components.declare_component(
        "tpstudio_review_preview",
        path=str(Path(__file__).with_name("review_preview_component")),
    )
    return component(
        html=document,
        selected=selected_id,
        scroll_request=scroll_request,
        default=None,
        key=key,
    )


def _navigate_annotation(
    state,
    choice_key: str,
    scroll_sequence_key: str,
    scroll_request_key: str,
    annotation_id: str,
) -> None:
    """Select one comment and explicitly request preview scrolling."""

    state[choice_key] = annotation_id
    sequence = int(state.get(scroll_sequence_key, 0)) + 1
    state[scroll_sequence_key] = sequence
    state[scroll_request_key] = {
        "annotation_id": annotation_id,
        "sequence": sequence,
    }


def _consume_preview_click_event(
    state, event, *, event_key: str, choice_key: str, valid_ids: tuple[str, ...],
) -> bool:
    """Apply one new component click exactly once."""

    if not isinstance(event, dict):
        return False
    annotation_id = event.get("annotation_id")
    event_id = event.get("event_id")
    if (
        annotation_id not in valid_ids
        or not event_id
        or event_id == state.get(event_key)
    ):
        return False
    state[event_key] = event_id
    state[choice_key] = annotation_id
    return True


def _consume_review_keyboard_event(state, event, *, event_key: str) -> str | None:
    """Return one new review keyboard action exactly once."""

    if not isinstance(event, dict):
        return None
    action = event.get("keyboard_action")
    event_id = event.get("event_id")
    if (
        action not in {"validate", "better", "worse", "previous", "next"}
        or not event_id
        or event_id == state.get(event_key)
    ):
        return None
    state[event_key] = event_id
    return action


def _validation_status_label(reviewed: int, total: int) -> str:
    if total <= 0:
        return "—"
    if reviewed >= total:
        return "✅ Vérifiée"
    if reviewed <= 0:
        return "À vérifier"
    return f"En cours ({reviewed}/{total})"


def _next_unverified_copy_id(
    progress: tuple[tuple[str, int, int, bool], ...], current_source_id: str,
) -> str | None:
    """Return the next non-reference copy whose review is incomplete."""

    source_ids = tuple(item[0] for item in progress)
    if current_source_id not in source_ids:
        return None
    start = source_ids.index(current_source_id)
    ordered = progress[start + 1:] + progress[:start]
    for source_id, reviewed, total, is_reference in ordered:
        if not is_reference and total > 0 and reviewed < total:
            return source_id
    return None


def _next_copy_id(
    progress: tuple[tuple[str, int, int, bool], ...], current_source_id: str,
) -> str | None:
    """Return the next non-reference copy in the displayed batch order."""

    student_ids = tuple(item[0] for item in progress if not item[3])
    if current_source_id not in student_ids:
        return None
    index = student_ids.index(current_source_id)
    return student_ids[index + 1] if index + 1 < len(student_ids) else None


def _restore_cached_reviews(st, analysis, source_id: str, copy_sha256: str):
    plan = build_annotation_plan(analysis)
    annotations = _ordered_review_annotations(plan)
    valid_ids = {annotation.annotation_id for annotation in annotations}
    current = get_annotation_reviews(st.session_state).get(source_id, ())
    merged = {}
    for review in load_shared_response_reviews(analysis.source.path, annotations):
        merged[review.annotation_id] = review
    copy_cached_reviews = load_annotation_reviews(copy_sha256, annotations)
    for review in copy_cached_reviews:
        merged[review.annotation_id] = review
    if copy_cached_reviews:
        # Seed the shared cache from validations produced before response-level
        # reuse was introduced. Existing identical entries are not rewritten.
        save_shared_response_reviews(
            analysis.source.path, copy_cached_reviews, annotations
        )
    for review in current:
        if review.annotation_id in valid_ids:
            merged[review.annotation_id] = review
    reviews = tuple(
        merged[annotation.annotation_id]
        for annotation in annotations
        if annotation.annotation_id in merged
    )
    if reviews != current:
        set_annotation_reviews_for_source(st.session_state, source_id, reviews)
    cached_by_id = {review.annotation_id: review for review in reviews}
    for annotation in annotations:
        review = cached_by_id.get(annotation.annotation_id)
        criterion_id = _annotation_grading_criterion(analysis, annotation)
        if (
            review is not None
            and review.level is not None
            and review.action is not AnnotationReviewAction.REMOVE
            and criterion_id is not None
        ):
            st.session_state.setdefault(
                _grading_widget_key(source_id, criterion_id),
                RubricLevel[review.level.name],
            )
    return plan, annotations, reviews


def _persist_cached_reviews(
    st, analysis, source_id: str, copy_sha256: str, annotations,
) -> None:
    reviews = get_annotation_reviews(st.session_state).get(source_id, ())
    save_annotation_reviews(copy_sha256, reviews, annotations)
    save_shared_response_reviews(analysis.source.path, reviews, annotations)


def _render_copy_review_workspace(
    st, analysis, source_id: str, copy_sha256: str,
    next_unverified_source_id: str | None = None,
    next_copy_source_id: str | None = None,
) -> None:
    """Render one corrected copy beside its teacher validation controls."""

    plan, annotations, reviews = _restore_cached_reviews(
        st, analysis, source_id, copy_sha256
    )
    review_by_id = {item.annotation_id: item for item in reviews}
    semantic_failures = sum(
        semantic.result is not None
        and any(
            diagnostic.startswith("SEMANTIC_PROVIDER_ERROR:")
            for diagnostic in semantic.result.diagnostics
        )
        for semantic in analysis.semantic_response_analyses
    )
    if semantic_failures:
        st.warning(
            f"{semantic_failures} réponse(s) scientifique(s) n'ont pas pu être "
            "analysées par l'IA. La liste des commentaires est incomplète."
        )
    validated = sum(item.annotation_id in review_by_id for item in annotations)
    st.caption(
        f"Commentaires examinés : {validated} / {len(annotations)} · "
        "la copie source reste inchangée"
    )

    preview_column, review_column = st.columns((2.2, 1.0), gap="large")
    annotation_ids = tuple(item.annotation_id for item in annotations)
    annotation_by_id = {item.annotation_id: item for item in annotations}
    choice_key = f"annotation-choice-{source_id}"
    scroll_sequence_key = f"annotation-scroll-sequence-{source_id}"
    scroll_request_key = f"annotation-scroll-request-{source_id}"
    current_selected = st.session_state.get(choice_key)
    if current_selected not in annotation_ids:
        current_selected = annotation_ids[0] if annotation_ids else None
        if current_selected is not None:
            st.session_state[choice_key] = current_selected

    signature = (
        analysis.source_id,
        analysis.source.path.stat().st_mtime_ns,
        _annotation_review_signature(reviews),
    )
    html = get_html_preview(st.session_state, source_id, signature)
    if html is None:
        html = render_analyzed_copy_html(
            analysis.source,
            analysis,
            options=CopyExportOptions(embed_images=True),
            annotation_reviews=reviews,
        )
        set_html_preview(st.session_state, source_id, signature, html)

    with preview_column:
        st.markdown("#### Copie corrigée")
        click_event = _review_preview_component(
            html,
            current_selected,
            scroll_request=st.session_state.pop(scroll_request_key, None),
            key=f"review-preview-{source_id}",
        )
    event_key = f"review-preview-event-{source_id}"
    if _consume_preview_click_event(
        st.session_state,
        click_event,
        event_key=event_key,
        choice_key=choice_key,
        valid_ids=annotation_ids,
    ):
        # The component was rendered earlier in this Streamlit pass with the
        # previous selection. Start one clean pass so both columns receive the
        # clicked annotation together.
        _rerun_copy_review(st, source_id)

    keyboard_event_key = f"review-keyboard-event-{source_id}"
    keyboard_action = _consume_review_keyboard_event(
        st.session_state,
        click_event,
        event_key=keyboard_event_key,
    )
    if keyboard_action is not None and annotations:
        selected_id = st.session_state[choice_key]
        selected_index = annotation_ids.index(selected_id)
        if keyboard_action in {"previous", "next"}:
            offset = -1 if keyboard_action == "previous" else 1
            target_index = max(0, min(len(annotation_ids) - 1, selected_index + offset))
            if target_index != selected_index:
                _navigate_annotation(
                    st.session_state,
                    choice_key,
                    scroll_sequence_key,
                    scroll_request_key,
                    annotation_ids[target_index],
                )
        elif keyboard_action in {"better", "worse"}:
            proposal = annotation_by_id[selected_id]
            current = review_by_id.get(selected_id)
            automatic_level = _SEVERITY_DEFAULT_REVIEW_LEVEL[proposal.severity.value]
            level_key = f"annotation-level-{source_id}-{selected_id}"
            pending_level_key = f"annotation-pending-level-{source_id}-{selected_id}"
            current_level = st.session_state.get(
                level_key,
                current.level
                if current is not None and current.level is not None
                else automatic_level,
            )
            levels = tuple(AnnotationReviewLevel)
            offset = 1 if keyboard_action == "better" else -1
            target_index = max(
                0, min(len(levels) - 1, levels.index(current_level) + offset)
            )
            # Streamlit warns when a widget key is assigned through session
            # state and the same widget is also created with an explicit
            # default. Carry the keyboard choice through a separate, one-shot
            # key and let the selectbox own its state on the following pass.
            st.session_state.pop(level_key, None)
            st.session_state[pending_level_key] = levels[target_index]
        else:
            proposal = annotation_by_id[selected_id]
            current = review_by_id.get(selected_id)
            level = st.session_state.get(
                f"annotation-level-{source_id}-{selected_id}",
                current.level
                if current is not None and current.level is not None
                else _SEVERITY_DEFAULT_REVIEW_LEVEL[proposal.severity.value],
            )
            action = st.session_state.get(
                f"annotation-action-{source_id}-{selected_id}",
                current.action if current is not None else AnnotationReviewAction.KEEP,
            )
            message = (
                st.session_state.get(f"annotation-message-{source_id}-{selected_id}")
                if action is AnnotationReviewAction.EDIT
                else None
            )
            criterion_id = _annotation_grading_criterion(analysis, proposal)
            if criterion_id is not None and action is not AnnotationReviewAction.REMOVE:
                st.session_state[_grading_widget_key(source_id, criterion_id)] = (
                    RubricLevel[level.name]
                )
            set_annotation_review(
                st.session_state,
                source_id,
                AnnotationReview(selected_id, action, message, level),
            )
            _persist_cached_reviews(
                st, analysis, source_id, copy_sha256, annotations,
            )
        _rerun_copy_review(st, source_id)

    selected_id = None
    with review_column:
        st.markdown("#### Validation des commentaires")
        if not annotations:
            st.info("Aucun commentaire automatique à valider.")
        elif validated < len(annotations) and st.button(
            "Tout conserver pour cette copie",
            key=f"annotation-keep-all-{source_id}",
        ):
            set_annotation_reviews_for_source(
                st.session_state,
                source_id,
                tuple(
                    review_by_id.get(item.annotation_id)
                    or AnnotationReview(
                        item.annotation_id, AnnotationReviewAction.KEEP
                    )
                    for item in annotations
                ),
            )
            _persist_cached_reviews(
                st, analysis, source_id, copy_sha256, annotations,
            )
            _rerun_copy_review(st, source_id)
        if annotations:
            selected_id = st.session_state[choice_key]
            selected_index = annotation_ids.index(selected_id)
            previous_column, position_column, next_column = st.columns((1, 1, 1))
            with previous_column:
                st.button(
                    "← Précédent",
                    disabled=selected_index == 0,
                    key=f"annotation-previous-{source_id}",
                    on_click=_navigate_annotation,
                    args=(
                        st.session_state,
                        choice_key,
                        scroll_sequence_key,
                        scroll_request_key,
                        annotation_ids[max(0, selected_index - 1)],
                    ),
                )
            with position_column:
                st.caption(f"{selected_index + 1} / {len(annotation_ids)}")
            with next_column:
                st.button(
                    "Suivant →",
                    disabled=selected_index == len(annotation_ids) - 1,
                    key=f"annotation-next-{source_id}",
                    on_click=_navigate_annotation,
                    args=(
                        st.session_state,
                        choice_key,
                        scroll_sequence_key,
                        scroll_request_key,
                        annotation_ids[min(len(annotation_ids) - 1, selected_index + 1)],
                    ),
                )
            proposal = annotation_by_id[selected_id]
            current = review_by_id.get(selected_id)
            default_action = (
                current.action if current is not None else AnnotationReviewAction.KEEP
            )
            st.caption("Proposition automatique")
            st.write(proposal.message)
            automatic_level = _SEVERITY_DEFAULT_REVIEW_LEVEL[
                proposal.severity.value
            ]
            current_level = (
                current.level
                if current is not None and current.level is not None
                else automatic_level
            )
            level_key = f"annotation-level-{source_id}-{selected_id}"
            pending_level_key = f"annotation-pending-level-{source_id}-{selected_id}"
            pending_level = st.session_state.pop(pending_level_key, None)
            if pending_level is not None:
                st.session_state.pop(level_key, None)
                current_level = pending_level
            level = st.selectbox(
                "Appréciation",
                tuple(AnnotationReviewLevel),
                index=tuple(AnnotationReviewLevel).index(current_level),
                format_func=_ANNOTATION_LEVEL_LABELS.get,
                key=level_key,
            )
            action = st.radio(
                "Décision",
                tuple(_ANNOTATION_REVIEW_LABELS),
                index=tuple(_ANNOTATION_REVIEW_LABELS).index(default_action),
                format_func=_ANNOTATION_REVIEW_LABELS.get,
                horizontal=True,
                key=f"annotation-action-{source_id}-{selected_id}",
            )
            message = None
            if action is AnnotationReviewAction.EDIT:
                message = st.text_area(
                    "Commentaire corrigé",
                    value=(current.message if current and current.message else proposal.message),
                    key=f"annotation-message-{source_id}-{selected_id}",
                )
            if st.button(
                "Enregistrer la décision",
                type="primary",
                key=f"annotation-save-{source_id}-{selected_id}",
            ):
                criterion_id = _annotation_grading_criterion(
                    analysis, proposal
                )
                if (
                    criterion_id is not None
                    and action is not AnnotationReviewAction.REMOVE
                ):
                    st.session_state[_grading_widget_key(
                        source_id, criterion_id
                    )] = RubricLevel[level.name]
                set_annotation_review(
                    st.session_state,
                    source_id,
                    AnnotationReview(selected_id, action, message, level),
                )
                _persist_cached_reviews(
                    st, analysis, source_id, copy_sha256, annotations,
                )
                saved_ids = {
                    item.annotation_id
                    for item in get_annotation_reviews(st.session_state).get(
                        source_id, ()
                    )
                }
                copy_is_complete = all(
                    annotation_id in saved_ids for annotation_id in annotation_ids
                )
                destination_source_id = (
                    next_unverified_source_id
                    if selected_index == len(annotation_ids) - 1
                    and copy_is_complete
                    and next_unverified_source_id is not None
                    else source_id
                )
                _rerun_copy_review(st, destination_source_id)

        if (
            analysis.project_id
            == FIRST_LAB_FORMATIVE_GRADING_PROFILE.project_id
        ):
            st.divider()
            _render_first_lab_grading(
                st,
                analysis,
                source_id,
                compact=True,
                annotations=annotations,
                reviews=get_annotation_reviews(st.session_state).get(source_id, ()),
                next_copy_source_id=next_copy_source_id,
            )



_RUBRIC_LEVEL_LABELS = {
    RubricLevel.ABSENT: "Absence de réponse",
    RubricLevel.TO_REVIEW: "À revoir",
    RubricLevel.PARTIAL: "Partiel",
    RubricLevel.GOOD: "Bien",
    RubricLevel.VERY_GOOD: "Très bien",
}


def _weighted_first_lab_score(levels_by_criterion, suggestions) -> Decimal:
    """Combine every reviewed answer while preserving rubric weights."""

    profile = FIRST_LAB_FORMATIVE_GRADING_PROFILE
    fallback_by_criterion = {
        item.decision.criterion_id: item.decision.level for item in suggestions
    }
    score = Decimal("0")
    for criterion in profile.criteria:
        levels = tuple(levels_by_criterion.get(criterion.criterion_id, ()))
        if levels:
            criterion_score = sum(
                (Decimal(4 + 4 * int(level)) for level in levels),
                Decimal("0"),
            ) / Decimal(len(levels))
        else:
            fallback = fallback_by_criterion[criterion.criterion_id]
            criterion_score = Decimal(4 + 4 * int(fallback))
        score += criterion.weight * criterion_score
    return score.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _render_first_lab_grading(
    st, analysis, source_id: str, *, compact: bool = False,
    annotations=(), reviews=(), next_copy_source_id: str | None = None,
) -> None:
    """Render a teacher-only, non-exported formative grading experiment."""

    profile = FIRST_LAB_FORMATIVE_GRADING_PROFILE
    if analysis.project_id != profile.project_id:
        return
    st.markdown("#### Note de la copie" if compact else "### Proposition de note formative")
    if not compact:
        st.caption(
            "Cette proposition dépend uniquement des niveaux choisis par "
            "l’enseignant et n’est pas ajoutée au corrigé étudiant."
        )
    suggestions = suggest_first_lab_rubric(analysis)
    reviewed_by_id = {item.annotation_id: item for item in tuple(reviews)}
    levels_by_criterion = {item.criterion_id: [] for item in profile.criteria}
    for annotation in tuple(annotations):
        criterion_id = _annotation_grading_criterion(analysis, annotation)
        if criterion_id not in levels_by_criterion:
            continue
        review = reviewed_by_id.get(annotation.annotation_id)
        if review is not None and review.action is AnnotationReviewAction.REMOVE:
            continue
        level = (
            review.level
            if review is not None and review.level is not None
            else _SEVERITY_DEFAULT_REVIEW_LEVEL[annotation.severity.value]
        )
        levels_by_criterion[criterion_id].append(RubricLevel[level.name])

    proposed_score = _weighted_first_lab_score(
        levels_by_criterion, suggestions
    )

    note_column, next_copy_column = st.columns((1.0, 1.0))
    with note_column:
        st.metric("Note proposée", f"{proposed_score}/20")
    with next_copy_column:
        st.button(
            "Copie suivante →",
            disabled=next_copy_source_id is None,
            key=f"next-copy-from-grade-{source_id}",
            on_click=(
                _rerun_copy_review if next_copy_source_id is not None else None
            ),
            args=(st, next_copy_source_id) if next_copy_source_id is not None else (),
        )


def _copy_issue_count(row, overview_rows=(), graph_rows=(), semantic_rows=()) -> int:
    """Count teacher-facing review signals for one compact copy row."""

    count = int(row.status != "Analysée" or bool(row.error_message))
    count += sum(item.severity.value in {"review", "error"} for item in overview_rows)
    count += sum(item.requires_human_review for item in graph_rows)
    count += sum(
        bool(item.contradictions)
        or any(criterion.status in {"partial", "not_found", "uncertain"} for criterion in item.criteria)
        for item in semantic_rows
    )
    return count


def _suggested_grade_label(analysis, annotations=(), reviews=()) -> str:
    """Return the automatic first-session proposal for the compact table."""

    if analysis is None or analysis.project_id != FIRST_LAB_FORMATIVE_GRADING_PROFILE.project_id:
        return "—"
    suggestions = suggest_first_lab_rubric(analysis)
    if annotations:
        reviewed_by_id = {item.annotation_id: item for item in tuple(reviews)}
        levels_by_criterion = {
            item.criterion_id: []
            for item in FIRST_LAB_FORMATIVE_GRADING_PROFILE.criteria
        }
        for annotation in tuple(annotations):
            criterion_id = _annotation_grading_criterion(analysis, annotation)
            if criterion_id not in levels_by_criterion:
                continue
            review = reviewed_by_id.get(annotation.annotation_id)
            if review is not None and review.action is AnnotationReviewAction.REMOVE:
                continue
            level = (
                review.level
                if review is not None and review.level is not None
                else _SEVERITY_DEFAULT_REVIEW_LEVEL[annotation.severity.value]
            )
            levels_by_criterion[criterion_id].append(RubricLevel[level.name])
        return f"{_weighted_first_lab_score(levels_by_criterion, suggestions)}/20"
    proposal = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        tuple(item.decision for item in suggestions),
    )
    return f"{proposal.proposed_score}/20"


def _build_semantic_provider(enabled: bool, *, environ=None):
    """Build a provider only from an explicit Analyze action."""
    if not enabled:
        return None
    environment = os.environ if environ is None else environ
    if not str(environment.get("OPENAI_API_KEY", "")).strip():
        return None
    model = _semantic_model()
    return CachedSemanticAnalysisProvider(
        OpenAISemanticAnalysisProvider(model=model),
        model=model,
    )


def web_error_message(exc: BaseException) -> str:
    text = str(exc)
    if isinstance(exc, WebInputError) and text.startswith("Notebook invalide : "):
        return text
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
            key=SEMANTIC_ANALYSIS_ENABLED_KEY,
        )
        semantic_model = _semantic_model()
        include_semantic_references = st.checkbox(
            "Analyser aussi les corrigés et énoncés de référence",
            value=False,
            disabled=not semantic_enabled,
            help=(
                "Désactivé par défaut : les références restent analysées localement, "
                "mais leurs réponses ne sont pas envoyées à OpenAI."
            ),
        )
        regenerate_graph_outputs = st.checkbox(
            "Régénérer les graphes absents",
            help=(
                "Exécute le code des copies étudiantes dans des fichiers temporaires. "
                "Les notebooks déposés restent inchangés. À n'activer que pour des "
                "copies provenant d'une source de confiance."
            ),
            key=REGENERATE_GRAPH_OUTPUTS_KEY,
        )
        if regenerate_graph_outputs:
            st.warning(
                "Le code des notebooks sera exécuté localement pour reconstruire "
                "les graphes que Basthon n'a pas enregistrés."
            )
        if semantic_enabled:
            st.caption(f"Modèle sémantique : {semantic_model}")
            st.caption(
                "Cache IA local actif : une réponse inchangée n'est pas "
                "renvoyée à OpenAI."
            )
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
                if identified.identity is not None and roster:
                    identified = replace(
                        identified,
                        identity=confirm_exact_roster_identity(identified.identity, roster),
                    )
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
        with st.expander(
            f"Copies du lot ({len(plan.sources)})",
            expanded=False,
        ):
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
                        progress = st.progress(0.0, text="Préparation de l’analyse…")

                        def update_progress(completed, total, source_id):
                            ratio = completed / total if total else 1.0
                            progress.progress(
                                ratio,
                                text=f"Copie {completed} sur {total} analysée",
                            )

                        try:
                            analysis_copies = tuple(copies)
                            execution_results = {}
                            if regenerate_graph_outputs:
                                progress.progress(
                                    0.0, text="Régénération des graphes absents…"
                                )
                                def update_graph_progress(
                                    completed, total, source_id, cached,
                                ):
                                    suffix = " (cache)" if cached else ""
                                    progress.progress(
                                        completed / total if total else 1.0,
                                        text=(
                                            f"Graphes : copie {completed} sur {total}"
                                            f"{suffix}"
                                        ),
                                    )

                                analysis_copies, execution_results = (
                                    regenerate_missing_graph_outputs(
                                        copies,
                                        progress_callback=update_graph_progress,
                                    )
                                )
                                if execution_results:
                                    incomplete = sum(
                                        not execution.success
                                        for execution in execution_results.values()
                                    )
                                    if incomplete:
                                        st.warning(
                                            f"Graphes régénérés partiellement pour {incomplete} "
                                            "copie(s) comportant des erreurs de code."
                                        )
                                    else:
                                        st.caption(
                                            f"Graphes régénérés dans {len(execution_results)} "
                                            "copie(s) temporaire(s), dont "
                                            f"{sum(item.cached for item in execution_results.values())} "
                                            "depuis le cache."
                                        )
                            if provider is None:
                                result = run_selected_dispatch(
                                    analysis_copies,
                                    progress_callback=update_progress,
                                )
                            else:
                                result = run_selected_dispatch(
                                    analysis_copies,
                                    semantic_provider=provider,
                                    include_semantic_references=include_semantic_references,
                                    progress_callback=update_progress,
                                )
                        finally:
                            progress.empty()
                    set_dispatch_result(
                        st.session_state,
                        result,
                        _analysis_signature(
                            signature,
                            semantic_enabled,
                            semantic_model,
                            include_semantic_references,
                            regenerate_graph_outputs,
                        ),
                    )
                clear_run_result(st.session_state)
                st.session_state[REVIEW_INDEX_KEY] = 0
            except Exception:
                clear_dispatch_result(st.session_state)
                st.error("Impossible d'analyser le lot.")
            finally:
                st.session_state[RUN_IN_PROGRESS_KEY] = False
        current_analysis_signature = _analysis_signature(
            signature,
            semantic_enabled,
            semantic_model,
            include_semantic_references,
            regenerate_graph_outputs,
        )
        invalidate_dispatch_if_signature_changed(st.session_state, current_analysis_signature)
        dispatch_result = get_current_dispatch_result(st.session_state, current_analysis_signature)
        if dispatch_result is not None:
            st.subheader("Résultat de l'analyse")
            overrides = get_project_overrides(st.session_state)
            rows = batch_dispatch_rows(dispatch_result, copies, overrides)
            export_results = get_export_results(st.session_state)
            from tpstudio.reporting import build_teacher_copy_report
            copy_views = []
            selected_by_id = {copy.source_id: copy for copy in copies}
            for row, item in zip(rows, dispatch_result.copies):
                active_analysis = active_analysis_for_source(
                    dispatch_result, overrides, item.source_id
                )
                report = (
                    build_teacher_copy_report(active_analysis)
                    if active_analysis is not None else None
                )
                overview_rows = (
                    build_teacher_scientific_overview(report).rows if report else ()
                )
                graphs = graph_summary_rows(report, key_prefix=item.source_id)
                semantics = semantic_response_rows(
                    item.dispatch.semantic_response_analyses if item.dispatch else (),
                    source_id=item.source_id,
                )
                selected_copy = selected_by_id.get(item.source_id)
                validation_reviewed = 0
                validation_total = 0
                validation_annotations = ()
                validation_reviews = ()
                if active_analysis is not None and selected_copy is not None:
                    _, validation_annotations, validation_reviews = (
                        _restore_cached_reviews(
                            st,
                            active_analysis,
                            item.source_id,
                            selected_copy.content_sha256,
                        )
                    )
                    validation_total = len(validation_annotations)
                    validation_reviewed = len(validation_reviews)
                identity_status = getattr(
                    getattr(selected_copy, "identity", None), "status", None
                )
                is_reference = getattr(identity_status, "value", "") in {
                    "reference_correction", "empty_statement"
                }
                copy_views.append({
                    "row": row,
                    "item": item,
                    "analysis": active_analysis,
                    "overview": overview_rows,
                    "graphs": graphs,
                    "semantics": semantics,
                    "issues": _copy_issue_count(row, overview_rows, graphs, semantics),
                    "reference": is_reference,
                    "validation": _validation_status_label(
                        validation_reviewed, validation_total
                    ),
                    "validation_reviewed": validation_reviewed,
                    "validation_total": validation_total,
                    "validation_annotations": validation_annotations,
                    "validation_reviews": validation_reviews,
                })

            attention_count = sum(
                view["issues"] > 0 and not view["reference"] for view in copy_views
            )
            ready_count = exportable_count(dispatch_result, overrides)
            metric_columns = st.columns(3)
            metric_columns[0].metric("Copies", len(copy_views))
            metric_columns[1].metric("À examiner", attention_count)
            metric_columns[2].metric("Prêtes à exporter", ready_count)

            show_all_copies = st.checkbox(
                "Afficher toutes les copies",
                value=False,
                key="show-all-analysis-copies",
                help="Inclut les copies sans alerte ainsi que les références.",
            )
            visible_views = (
                copy_views if show_all_copies else [
                    view for view in copy_views
                    if view["issues"] > 0 and not view["reference"]
                ]
            )
            if not visible_views:
                st.success("Aucune copie étudiante ne nécessite actuellement de vérification.")
                visible_views = [view for view in copy_views if not view["reference"]] or copy_views

            with st.expander("Tableau récapitulatif du lot", expanded=False):
                st.dataframe(
                    [
                        {
                            "Fichier": view["row"].display_name,
                            "TP": view["row"].project_title or "—",
                            "État": view["row"].status,
                            "Validation": view["validation"],
                            "Points à examiner": view["issues"],
                            "Note proposée": _suggested_grade_label(
                                view["analysis"],
                                view["validation_annotations"],
                                view["validation_reviews"],
                            ),
                        }
                        for view in visible_views
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
            view_ids = tuple(view["item"].source_id for view in visible_views)
            views_by_id = {view["item"].source_id: view for view in visible_views}
            _restore_reviewed_copy(st.session_state, view_ids)
            selected_source_id = st.selectbox(
                "Copie à examiner",
                view_ids,
                format_func=lambda source_id: (
                    f"{views_by_id[source_id]['validation']} — "
                    f"{views_by_id[source_id]['row'].display_name}"
                ),
                key=_ACTIVE_ANALYSIS_COPY_KEY,
            )
            selected_view = views_by_id[selected_source_id]
            review_progress = tuple(
                (
                    view["item"].source_id,
                    view["validation_reviewed"],
                    view["validation_total"],
                    view["reference"],
                )
                for view in visible_views
            )
            next_unverified_source_id = _next_unverified_copy_id(
                review_progress, selected_source_id
            )
            next_copy_source_id = _next_copy_id(
                review_progress, selected_source_id
            )
            row = selected_view["row"]
            item = selected_view["item"]
            active_analysis = selected_view["analysis"]
            overview_rows = selected_view["overview"]
            graph_rows = selected_view["graphs"]
            semantic_rows = selected_view["semantics"]

            st.markdown(f"### {row.display_name}")
            if active_analysis is not None:
                _render_copy_review_workspace(
                    st,
                    active_analysis,
                    item.source_id,
                    selected_by_id[item.source_id].content_sha256,
                    next_unverified_source_id,
                    next_copy_source_id,
                )
            else:
                st.info("Aucun aperçu corrigé n'est disponible pour cette copie.")

            with st.expander("Options d'export du lot", expanded=False):
                st.caption(
                    "Un seul fichier HTML autonome sera créé par copie. Il pourra "
                    "être joint directement à un courriel."
                )
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
                overwrite = st.checkbox(
                    "Autoriser le remplacement des fichiers existants",
                    value=True,
                    key="export-overwrite",
                )
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
                                annotation_reviews=get_annotation_reviews(
                                    st.session_state
                                ),
                            ),
                        )
                        st.session_state.pop(_MAIL_DRAFTS_KEY, None)
                        st.rerun()
                    except (TypeError, ValueError, OSError) as exc:
                        st.error(web_error_message(exc))

                successful_exports = {
                    source_id: state.result
                    for source_id, state in export_results.items()
                    if state.result is not None and state.result.html_generated
                }
                if successful_exports:
                    st.divider()
                    st.markdown("#### Transmission aux étudiants")
                    st.caption(
                        "TPStudio prépare uniquement des brouillons .eml. "
                        "Aucun courriel n'est envoyé automatiquement."
                    )
                    sender_email = st.text_input(
                        "Adresse d'expédition",
                        value=load_sender_email(),
                        placeholder="professeur@exemple.fr",
                        key="mail-drafts-sender-email",
                        help=(
                            "Cette adresse est enregistrée uniquement sur ce Mac "
                            "et ajoutée au champ De des brouillons."
                        ),
                    )
                    overwrite_drafts = st.checkbox(
                        "Remplacer les brouillons existants",
                        value=False,
                        key="mail-drafts-overwrite",
                    )
                    if st.button(
                        "Préparer les brouillons de courriel",
                        key="prepare-mail-drafts",
                    ):
                        drafts = {}
                        errors = {}
                        try:
                            save_sender_email(sender_email)
                        except (TypeError, ValueError, OSError) as exc:
                            st.error(str(exc) or type(exc).__name__)
                            st.session_state[_MAIL_DRAFTS_KEY] = ({}, {})
                            st.stop()
                        for source_id, export_result in successful_exports.items():
                            selected_copy = selected_by_id.get(source_id)
                            view = next(
                                (
                                    candidate for candidate in copy_views
                                    if candidate["item"].source_id == source_id
                                ),
                                None,
                            )
                            try:
                                if selected_copy is None or selected_copy.identity is None:
                                    raise ValueError("L'identité de la copie est absente.")
                                if view is None or view["analysis"] is None:
                                    raise ValueError("L'analyse de la copie est absente.")
                                mail_identity = enrich_identity_for_mail(
                                    selected_copy.identity,
                                    selected_copy.original_filename,
                                    roster,
                                )
                                drafts[source_id] = prepare_correction_mail_draft(
                                    source_id=source_id,
                                    identity=mail_identity,
                                    html_path=export_result.html_artifact.path,
                                    output_dir=export_result.html_artifact.path.parent / "Brouillons",
                                    tp_title=view["analysis"].project.identity.title,
                                    sender_email=sender_email,
                                    overwrite=overwrite_drafts,
                                )
                            except (TypeError, ValueError, FileNotFoundError, OSError) as exc:
                                errors[source_id] = str(exc) or type(exc).__name__
                        st.session_state[_MAIL_DRAFTS_KEY] = (drafts, errors)

                    drafts, draft_errors = st.session_state.get(
                        _MAIL_DRAFTS_KEY, ({}, {})
                    )
                    if drafts:
                        st.success(f"{len(drafts)} brouillon(s) prêt(s).")
                        for source_id, draft in drafts.items():
                            draft_label = " · ".join(draft.student_names)
                            download_column, mail_column = st.columns(2)
                            with download_column:
                                st.download_button(
                                    "Télécharger le brouillon — " + draft_label,
                                    data=draft.draft_path.read_bytes(),
                                    file_name=draft.draft_path.name,
                                    mime="message/rfc822",
                                    key=f"download-mail-draft-{source_id}",
                                )
                            with mail_column:
                                if st.button(
                                    "Ouvrir dans Mail — " + draft_label,
                                    key=f"open-apple-mail-draft-{source_id}",
                                ):
                                    try:
                                        open_correction_mail_in_apple_mail(draft)
                                    except (TypeError, ValueError, FileNotFoundError, OSError) as exc:
                                        st.error(str(exc) or type(exc).__name__)
                                    else:
                                        st.success(
                                            "Le courriel est ouvert dans Mail. "
                                            "Vérifiez-le puis cliquez sur Envoyer."
                                        )
                    for source_id, message in draft_errors.items():
                        display_name = selected_by_id.get(source_id)
                        label = (
                            display_name.original_filename
                            if display_name is not None else source_id
                        )
                        st.warning(f"{label} : {message}")
    if st.button("Réinitialiser"):
        workspace.reset()
        reset_web_session(st.session_state)
        st.rerun()


if __name__ == "__main__":
    main()
