from __future__ import annotations
from dataclasses import dataclass
from typing import Any

FactName=str
RuleId=str
DiagnosticCode=str
Operator=str

@dataclass(slots=True)
class Location:
    cell_index:int
    section:str|None=None

@dataclass(slots=True)
class Fact:
    name:FactName
    value:Any
    source:str|None=None
    location:Location|None=None

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
