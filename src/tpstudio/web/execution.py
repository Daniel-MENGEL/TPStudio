"""Execution adapter for the prepared A71g batch; no scientific logic."""

from __future__ import annotations

from tpstudio.batch import BatchPlan, BatchRunResult, run_snells_laws_batch


def run_prepared_batch(plan: BatchPlan) -> BatchRunResult:
    if type(plan) is not BatchPlan:
        raise TypeError("Le lancement web exige un BatchPlan.")
    return run_snells_laws_batch(plan)


def can_run_batch(selected_copies, plan) -> tuple[bool, tuple[str, ...]]:
    if plan is None:
        return False, ("Lot non vérifié.",)
    copies = tuple(selected_copies)
    if not copies:
        return False, ("Aucune copie sélectionnée.",)
    if tuple(item.source_id for item in copies) != tuple(source.source_id for source in plan.sources):
        return False, ("Le lot préparé est périmé.",)
    reasons = []
    for item in copies:
        identity = item.identity
        if identity is None or identity.status.value == "missing":
            reasons.append("Certaines identités sont manquantes.")
        elif identity.status.value == "to_review":
            reasons.append("Certaines identités doivent être vérifiées avant correction.")
    return (not reasons, tuple(dict.fromkeys(reasons)))
