"""Contrato comum a todos os gates.

Todo gate devolve um ``GateResult`` cujo ``status`` ('pass'|'fail'|'skipped')
é consumido por state.py e pela CLI. O schema de ``details`` é livre por gate,
mas sempre deve incluir ``issues`` (lista de ``Issue``) para diagnóstico.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

GateStatus = Literal["pass", "fail", "skipped"]
Phase = Literal[
    "requirements", "bdd", "tests", "implementation",
    "refactor", "review", "done",
]


@dataclass
class Issue:
    severity: Literal["error", "warning", "info"] = "error"
    code: str = ""
    message: str = ""
    line: int | None = None
    col: int | None = None
    context: str = ""


@dataclass
class GateResult:
    name: str
    phase: Phase
    status: GateStatus
    issues: list[Issue] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "phase": self.phase,
            "status": self.status,
            "issues": [i.__dict__ for i in self.issues],
            "details": self.details,
        }


def pass_(name: str, phase: Phase, details: dict | None = None, issues: list[Issue] | None = None) -> GateResult:
    return GateResult(name=name, phase=phase, status="pass", details=details or {}, issues=issues or [])


def fail(name: str, phase: Phase, issues: list[Issue], details: dict | None = None) -> GateResult:
    return GateResult(
        name=name,
        phase=phase,
        status="fail",
        issues=issues,
        details=details or {},
    )
