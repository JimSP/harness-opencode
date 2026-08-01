"""Despacha gates: conhece projeto ativo, config, e persiste resultado no state.json.

Centraliza o fluxo: carrega .engineer-hq.toml do projeto ativo → localiza
artefato da feature → invoca gate correto → grava GateRecord no state.json →
retorna GateResult.
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from . import workspace as ws_mod
from .schema import EhqError, GateRecord, ProjectState, project_paths
from .gates.base import GateResult
from .gates import ears_gate as ears_gate
from .gates import gherkin_gate


def _require_active(ws) -> tuple[str, Path]:
    pid = ws.active_project
    if not pid:
        raise EhqError(
            "nenhum projeto ativo",
            missing=["chame `ehq project use <id>` ou `ehq project add ...`"],
        )
    return pid, Path(ws.projects[pid].path)


def _load_config(project_root: Path) -> dict[str, Any]:
    cfg_path = project_paths(project_root)["config"]
    try:
        with cfg_path.open("rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        raise EhqError(
            f".engineer-hq.toml ausente em {cfg_path}",
            missing=["rode `ehq project add ...` para reinicializar"],
        )
    except tomllib.TOMLDecodeError as exc:
        raise EhqError(f".engineer-hq.toml inválido: {exc}") from exc


def _load_state(project_root: Path) -> tuple[ProjectState, Path]:
    state_path = project_paths(project_root)["state"]
    if not state_path.exists():
        raise EhqError(f"state.json ausente: {state_path}")
    st = ProjectState.model_validate(json.loads(state_path.read_text(encoding="utf-8")))
    return st, state_path


def _save_state(state_path: Path, st: ProjectState) -> None:
    payload = st.model_dump(mode="json", by_alias=True)
    tmp = state_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    tmp.replace(state_path)


def _gate_config(cfg: dict, gate_name: str) -> dict[str, Any]:
    gates = cfg.get("gate", {})
    return gates.get(gate_name, {})


_GATES_BY_PHASE = {
    "requirements": {"ears": ears_gate},
    "bdd": {"gherkin": gherkin_gate},
    # fases futuras: tests, implementation, refactor, review
}


def run_gate(
    ws,
    *,
    gate_name: str,
    feature_id: str,
    persist: bool = True,
) -> dict[str, Any]:
    """Executa um gate; persiste em state.json; retorna dict JSON-sériaável."""
    from datetime import datetime

    pid, root = _require_active(ws)
    cfg = _load_config(root)
    st, state_path = _load_state(root)
    if feature_id not in st.features:
        raise EhqError(
            f"feature inexistente: {feature_id}",
            missing=list(st.features.keys()) or ["(sem features)"],
        )
    fs = st.features[feature_id]

    # encontra implementação do gate
    impl = None
    for impls in _GATES_BY_PHASE.values():
        if gate_name in impls:
            impl = impls[gate_name]
            break
    if impl is None:
        raise EhqError(
            f"gate desconhecido: {gate_name}",
            missing=["ear", "gherkin", "aaa", "redgreen", "refactor", "all"],
        )

    # localiza artefato
    if gate_name == "ears":
        rel = fs.artifacts.req
        if not rel:
            return _emit_error(
                st, state_path, fs, gate_name, "EARS_NO_REQ_ARTIFACT",
                "feature sem .req.md (artifacts.req vazio). rode `ehq state new`.",
                persist,
            )
        artifact = root / rel
        result = impl.run(artifact, _gate_config(cfg, "ears"))
    elif gate_name == "gherkin":
        rel = fs.artifacts.feature
        if not rel:
            return _emit_error(
                st, state_path, fs, gate_name, "GHERKIN_NO_FEATURE_ARTIFACT",
                "feature sem .feature (artifacts.feature vazio). subagent ehq-bdd deve produzi-lo.",
                persist,
            )
        artifact = root / rel
        result = impl.run(artifact, _gate_config(cfg, "gherkin"))
    else:
        raise EhqError(f"gate '{gate_name}' não implementado ainda")

    # persiste GateRecord
    rec = GateRecord(
        name=result.name,
        phase=result.phase,  # type: ignore[arg-type]
        status=result.status,  # type: ignore[arg-type]
        at=datetime.now().astimezone(),
        details=result.details,
    )
    # evita duplicar gate igual consecutivo: remove último se mesmo nome/status/atualiza
    if persist:
        # simplificação: remove registros anteriores com mesmo nome (mantém só o último)
        fs.gates = [g for g in fs.gates if g.name != result.name]
        fs.gates.append(rec)
        fs.updated_at = datetime.now().astimezone()
        _save_state(state_path, st)

    out = result.to_dict()
    out["project_id"] = pid
    out["feature_id"] = feature_id
    if result.status == "pass":
        fs_phase = fs.phase
        if fs_phase == "requirements":
            out["next_phase_hint"] = "bdd"
        elif fs_phase == "bdd":
            out["next_phase_hint"] = "tests"
        else:
            out["next_phase_hint"] = None
    else:
        out["next_phase_hint"] = None
    return out


def _emit_error(
    st: ProjectState,
    state_path: Path,
    fs,
    gate_name: str,
    code: str,
    message: str,
    persist: bool,
) -> dict[str, Any]:
    from datetime import datetime

    result_dict = {
        "name": gate_name,
        "phase": fs.phase,
        "status": "fail",
        "issues": [{"severity": "error", "code": code, "message": message}],
        "details": {},
    }
    if persist:
        rec = GateRecord(
            name=gate_name,
            phase=fs.phase,  # type: ignore[arg-type]
            status="fail",  # type: ignore[arg-type]
            at=datetime.now().astimezone(),
            details={"error": code},
        )
        fs.gates = [g for g in fs.gates if g.name != gate_name]
        fs.gates.append(rec)
        fs.updated_at = datetime.now().astimezone()
        _save_state(state_path, st)
    return {
        **result_dict,
        "project_id": st.project_id,
        "feature_id": next(
            (fid for fid, f in st.features.items() if f is fs), "<unknown>"
        ),
        "next_phase_hint": None,
    }
