"""Compatibility models predating the A63 fact infrastructure.

New code should import :class:`Fact` from :mod:`tpstudio.reasoning.facts`.
The remaining classes stay here until the rules milestone defines their final
contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .facts import Fact

FactName=str
RuleId=str
DiagnosticCode=str
Operator=str

@dataclass(slots=True)
class Location:
    cell_index:int
    section:str|None=None

@dataclass(slots=True)
class Condition:
    fact:FactName
    operator:Operator
    expected_value:Any

@dataclass(slots=True)
class Rule:
    id:RuleId
    description:str
    conditions:list[Condition]

@dataclass(slots=True)
class Diagnostic:
    code:DiagnosticCode
    message:str
    rule_id:RuleId
    location:Location|None=None
