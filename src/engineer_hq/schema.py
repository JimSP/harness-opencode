"""Modelos compartilhados (Pydantic) para workspace, projetos e estado.

Centraliza os schemas que workspace.py/project.py/state.py leem/escrevem.
Qualquer mudança estrutural de workspace.toml ou state.json começa aqui.

Convenções de ID:
- Projeto:  PRJ-<seq4>-<slug>
- Frente:   FR-<seq4>-<slug>
- Feature:  FT-<seq4>-<slug>  (dentro de state.json por projeto)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---- Enums / aliases ---------------------------------------------------------

Lang = Literal["python", "java", "rust", "auto"]
FrontKind = Literal["research", "spike", "code-review", "misc"]
FrontStatus = Literal["open", "in-progress", "blocked", "done"]

Phase = Literal[
    "requirements",
    "bdd",
    "tests",
    "implementation",
    "refactor",
    "review",
    "done",
]
GateStatus = Literal["pass", "fail", "skipped"]
ProfileName = Literal["strict", "relaxed", "legacy"]


# ---- Workspace (workspace.toml) ---------------------------------------------


class ProjectRef(BaseModel):
    """Entrada de um projeto no índice do workspace."""

    model_config = ConfigDict(extra="forbid")

    name: str
    path: str
    language: Lang = "auto"
    profile: ProfileName = "strict"
    created_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    notes: str = ""


class FrontRef(BaseModel):
    """Frente não-feature no workspace (status-only)."""

    model_config = ConfigDict(extra="forbid")

    kind: FrontKind = "misc"
    title: str
    status: FrontStatus = "open"
    created_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    related_projects: list[str] = Field(default_factory=list)
    notes: str = ""


class Workspace(BaseModel):
    """Raiz do workspace.toml."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    owner: str = ""
    active_project: str | None = None
    projects: dict[str, ProjectRef] = Field(default_factory=dict)
    fronts: dict[str, FrontRef] = Field(default_factory=dict)


# ---- Estado por projeto (state.json) ----------------------------------------


class ArtifactPaths(BaseModel):
    """Caminhos dos artefatos produzidos por feature."""

    model_config = ConfigDict(extra="forbid")

    req: str | None = None
    feature: str | None = None
    tests: list[str] = Field(default_factory=list)
    impl: list[str] = Field(default_factory=list)


class GateRecord(BaseModel):
    """Resultado de um gate rodado."""

    model_config = ConfigDict(extra="forbid")

    name: str
    phase: Phase
    status: GateStatus
    at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    details: dict = Field(default_factory=dict)


class TransitionRecord(BaseModel):
    """Item do transition_log de uma feature."""

    model_config = ConfigDict(extra="forbid")

    from_: Phase = Field(alias="from")
    to: Phase
    at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    gate: str | None = None
    by: str = "orchestrator"
    diagnose: dict | None = None


class FeatureState(BaseModel):
    """Estado de uma feature dentro do state.json de um projeto."""

    model_config = ConfigDict(extra="forbid")

    title: str
    phase: Phase = "requirements"
    language: Lang = "auto"
    created_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    updated_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    artifacts: ArtifactPaths = Field(default_factory=ArtifactPaths)
    gates: list[GateRecord] = Field(default_factory=list)
    transition_log: list[TransitionRecord] = Field(default_factory=list)


class GlobalGateCache(BaseModel):
    """Cache do ultimo gate_all rodado."""

    model_config = ConfigDict(extra="forbid")

    last_run_at: datetime | None = None
    status: GateStatus | None = None
    details: dict = Field(default_factory=dict)


class ProjectState(BaseModel):
    """Raiz do state.json por projeto."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    project_id: str
    workspace_path: str
    active_profile: ProfileName = "strict"
    features: dict[str, FeatureState] = Field(default_factory=dict)
    global_gate_cache: GlobalGateCache = Field(default_factory=GlobalGateCache)


# ---- Erros autoritativos -----------------------------------------------------


class EhqError(Exception):
    """Erro que a CLI traduz em exit 2 + JSON estruturado."""

    def __init__(
        self,
        error: str,
        *,
        current_phase: str | None = None,
        required_phase: str | None = None,
        missing: list[str] | None = None,
        **extra: object,
    ) -> None:
        super().__init__(error)
        self.error = error
        self.current_phase = current_phase
        self.required_phase = required_phase
        self.missing = missing or []
        self.extra = extra


def workspace_config_path() -> Path:
    """Caminho canônico do workspace.toml."""
    return Path.home() / ".config" / "engineer-hq" / "workspace.toml"


def roadmap_path() -> Path:
    """Caminho canônico do ROADMAP.md (fonte da verdade de progresso)."""
    return Path.home() / ".config" / "engineer-hq" / "ROADMAP.md"


def project_paths(project_root: Path) -> dict[str, Path]:
    """Caminhos esperados dentro de um projeto-alvo."""
    base = project_root / ".engineer-hq"
    return {
        "config": project_root / ".engineer-hq.toml",
        "state": base / "state.json",
        "specs": base / "specs",
        "gen": base / "gen",
        "reports": base / "reports",
    }
