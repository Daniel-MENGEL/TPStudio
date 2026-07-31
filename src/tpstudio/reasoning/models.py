"""Compatibility models predating the A63 fact infrastructure.

New code should import :class:`Fact` from :mod:`tpstudio.reasoning.facts`.
The remaining classes stay here until the rules milestone defines their final
contracts.
"""

from __future__ import annotations

from dataclasses import dataclass

from .conditions import Condition
from .diagnostics import Diagnostic
from .facts import Fact
from .rules import Rule

FactName=str
RuleId=str
DiagnosticCode=str
Operator=str

@dataclass(slots=True)
class Location:
    cell_index:int
    section:str|None=None
