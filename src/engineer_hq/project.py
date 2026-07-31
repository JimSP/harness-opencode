"""Gestão de projetos no workspace: add/list/use/info.

Registra projetos no workspace.toml e gera a estrutura mínima
(.engineer-hq.toml + state.json) dentro de cada projeto-alvo.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w

from .schema import (
    EhqError,
    ProjectRef,
    ProjectState,
    Workspace,
    project_paths,
)
from . import workspace as ws_mod

# ---- Helpers de ID/slug -----------------------------------------------------

_SEQ_RE = re.compile(r"^PRJ-(\d{4})-")


def _slugify(title: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    return s or "proj"


def _next_project_id(ws: Workspace, title: str) -> str:
    max_seq = 0
    for pid in ws.projects:
        m = _SEQ_RE.match(pid)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"PRJ-{max_seq + 1:04d}-{_slugify(title)}"


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str).expanduser().resolve()
    if not p.exists():
        raise EhqError(f"path inexistente: {p}")
    if not p.is_dir():
        raise EhqError(f"path não é diretório: {p}")
    return p


# ---- Geração de estrutura no projeto-alvo (A.5) -----------------------------

_DEFAULT_CONFIG_TOML = """\
version = 1
profile = "strict"
languages = ["auto"]
specs_dir = ".engineer-hq/specs"
state_file = ".engineer-hq/state.json"
gen_dir = ".engineer-hq/gen"

profiles = ["strict", "relaxed", "legacy"]

[gate.ears]
require_ears_format = true
require_unambiguous = true
require_dod_section = true

[gate.gherkin]
require_format = true
require_scenario_outline = true
require_req_ref = true

[gate.aaa]
require_pattern = true
require_failure_first = true
min_cases_per_scenario = 1
require_feature_ref = true

[gate.redgreen]
tests_pass = true
no_new_lint_errors = true
compile_ok = true

[gate.refactor]
no_metric_regression = true
no_lint_regression = true
tests_pass = true

[gate.all]
min_coverage = 90
min_mutation_score = 80
max_complexity = 10
max_cognitive = 15
max_halstead_effort = 1000
critical_sca_count = 0
high_secmisconfig_count = 0
no_secrets_detected = true

[scanning]
semgrep = true
osv_scanner = true
gitleaks = true
trivy = false
"""


def _bootstrap_project_files(project_root: Path, project_id: str, profile: str) -> None:
    """Cria .engineer-hq.toml + state.json + dirs; idempotente."""
    paths = project_paths(project_root)
    cfg_path = paths["config"]
    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(_DEFAULT_CONFIG_TOML, encoding="utf-8")
        if profile != "strict":
            with cfg_path.open("rb") as fh:
                cfg = tomllib.load(fh)
            cfg["profile"] = profile
            with cfg_path.open("wb") as fh:
                tomli_w.dump(cfg, fh)
        # valida imediatamente para pegar regressão de schema aqui
        with cfg_path.open("rb") as fh:
            tomllib.load(fh)
    state_path = paths["state"]
    if not state_path.exists():
        state_path.parent.mkdir(parents=True, exist_ok=True)
        st = ProjectState(
            project_id=project_id,
            workspace_path=str(project_root),
            active_profile=profile,  # type: ignore[arg-type]
        )
        _write_state(state_path, st)
    for key in ("specs", "gen", "reports"):
        p = paths[key]
        p.mkdir(parents=True, exist_ok=True)
    # .gitignore dentro do projeto para gen/reports, se ausente
    gi = project_root / ".gitignore"
    ignore_line = ".engineer-hq/gen/\n.engineer-hq/reports/\n"
    if gi.exists():
        cur = gi.read_text(encoding="utf-8", errors="ignore")
        if ".engineer-hq/gen/" not in cur:
            gi.write_text(cur.rstrip() + "\n" + ignore_line, encoding="utf-8")
    else:
        gi.write_text(ignore_line, encoding="utf-8")


def _write_state(path: Path, state: ProjectState) -> None:
    import json

    payload = state.model_dump(mode="json", by_alias=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _read_state(path: Path) -> ProjectState | None:
    import json

    if not path.exists():
        return None
    try:
        return ProjectState.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


# ---- API pública ------------------------------------------------------------


@dataclass
class AddResult:
    project_id: str
    path: str
    created_files: list[str]


def add_project(
    ws: Workspace,
    *,
    path: str,
    name: str | None = None,
    language: str = "auto",
    profile: str = "strict",
) -> AddResult:
    """Registra projeto no ws e gera arquivos mínimos em <path>/.engineer-hq.

    Recusa se path já está em uso por outro project_id.
    """
    root = _resolve_path(path)
    # checa duplicidade por path absoluto
    for pid, pref in ws.projects.items():
        if Path(pref.path).resolve() == root:
            raise EhqError(
                f"path já registrado como {pid}",
                **{"conflicting_project_id": pid},
            )
    title_name = name or root.name
    pid = _next_project_id(ws, title_name)
    _bootstrap_project_files(root, pid, profile)
    ws.projects[pid] = ProjectRef(
        name=title_name,
        path=str(root),
        language=language,  # type: ignore[arg-type]
        profile=profile,  # type: ignore[arg-type]
    )
    ws.active_project = pid  # add implica tornar ativo
    ws_mod.save_workspace(ws)
    created = [
        str((root / ".engineer-hq.toml").relative_to(root.parent if root.parent != root else root)),
        ".engineer-hq/state.json",
    ]
    return AddResult(project_id=pid, path=str(root), created_files=created)


def list_projects(ws: Workspace) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pid, pref in ws.projects.items():
        st = _read_state(project_paths(Path(pref.path))["state"])
        features_count = len(st.features) if st else 0
        out.append(
            {
                "project_id": pid,
                "name": pref.name,
                "path": pref.path,
                "language": pref.language,
                "profile": pref.profile,
                "active": ws.active_project == pid,
                "features_count": features_count,
                "accessible": Path(pref.path).exists(),
            }
        )
    return out


def use_project(ws: Workspace, project_id: str) -> dict[str, Any]:
    """Seta projeto ativo; valida existence/access."""
    ws_mod.set_active_project(ws, project_id)
    ws_mod.save_workspace(ws)
    pref = ws.projects[project_id]
    return {
        "project_id": project_id,
        "name": pref.name,
        "path": pref.path,
        "active": True,
    }


def project_info(ws: Workspace, project_id: str | None = None) -> dict[str, Any]:
    """Dump consolidado do projeto ativo (ou <project_id> informado)."""
    pid = project_id or ws.active_project
    if not pid:
        raise EhqError("nenhum projeto ativo", missing=["chame `ehq project use <id>`"])
    if pid not in ws.projects:
        raise EhqError(f"projeto desconhecido: {pid}", missing=list(ws.projects.keys()))
    pref = ws.projects[pid]
    paths = project_paths(Path(pref.path))
    st = _read_state(paths["state"])
    config_exists = paths["config"].exists()
    features: list[dict[str, Any]] = []
    last_gate = None
    if st:
        for fid, fs in st.features.items():
            features.append(
                {
                    "feature_id": fid,
                    "title": fs.title,
                    "phase": fs.phase,
                    "updated_at": fs.updated_at.isoformat(),
                }
            )
            if fs.gates:
                g = fs.gates[-1]
                last_gate = {
                    "feature_id": fid,
                    "gate": g.name,
                    "status": g.status,
                    "at": g.at.isoformat(),
                }
    return {
        "project_id": pid,
        "name": pref.name,
        "path": pref.path,
        "language": pref.language,
        "profile": pref.profile,
        "config_exists": config_exists,
        "state_exists": paths["state"].exists(),
        "features": features,
        "features_count": len(features),
        "last_gate": last_gate,
    }


def active_project_id(ws: Workspace) -> str | None:
    return ws.active_project
