"""Shared models for deterministic scientific evaluation."""

from enum import Enum


class EvaluationStatus(str, Enum):
    """Outcome of one internal evaluation criterion."""

    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    NOT_APPLICABLE = "not_applicable"
    DEFERRED = "deferred"
