"""Shared presentation metadata for configurable feedback."""

from enum import Enum


class FeedbackAudience(str, Enum):
    """Intended recipient of one feedback item."""

    STUDENT = "student"
    TEACHER = "teacher"


class FeedbackPriority(str, Enum):
    """Relative presentation priority, independent of scoring."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
