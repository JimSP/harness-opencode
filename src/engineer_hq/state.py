"""Operações de state.json por projeto: new/show/advance/regress.

Tudo opera sobre o projeto ATIVO no workspace. Sem projeto ativo -> EhqError.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schema import (
    ArtifactPaths,
    EhqError,
    FeatureState,
    Phase,
    ProjectState,
    TransitionRecord,
    project_paths,
)
from . import workspace as ws_mod

_SEQ_RE = re.compile(r"^FT-(\d{4})-")
_PHASES: tuple[Phase, ...] = (
    "requirements",
    "bdd",
    "tests",
    "implementation",
    "refactor",
    "review",
    "done",
)


def _require_active(ws) -> tuple[str, Path]:
    pid = ws.active_project
    if not pid:
        raise EhqError(
            "nenhum projeto ativo",
            missing=["chame `ehq project use <id>` ou `ehq project add ...`"],
        )
    pref = ws.projects[pid]
    return pid, Path(pref.path)


def _load_state(root: Path) -> tuple[ProjectState, Path]:
    paths = project_paths(root)
    state_path = paths["state"]
    if not state_path.exists():
        raise EhqError(
            f"state.json ausente em {state_path}",
            missing=["rode `ehq project add ...` para reinicializar"],
            **{"project_id": root.name},
        )
    try:
        st = ProjectState.model_validate(json.loads(state_path.read_text(encoding="utf-8")))
    except Exception as exc:
        raise EhqError(f"state.json inválido: {exc}") from exc
    return st, state_path


def _save_state(state_path: Path, st: ProjectState) -> None:
    payload = st.model_dump(mode="json", by_alias=True)
    tmp = state_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    tmp.replace(state_path)


def _next_feature_id(st: ProjectState, title: str) -> str:
    max_seq = 0
    for fid in st.features:
        m = _SEQ_RE.match(fid)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-") or "feat"
    return f"FT-{max_seq + 1:04d}-{slug}"


def _touch_req_skeleton(project_root: Path, feature_id: str, title: str) -> str:
    paths = project_paths(project_root)
    specs = paths["specs"]
    specs.mkdir(parents=True, exist_ok=True)
    req_path = specs / f"{feature_id}.req.md"
    if not req_path.exists():
        req_path.write_text(
            f"# {title}\n\n> feature: {feature_id}\n> status: rascunho (fase: requirements)\n\n"
            "## Requisito\n\n<!-- Escreva em EARS. Ex: \"O sistema deve ...\" / "
            "\"Quando <gatilho>, o sistema deve <resposta>\" -->\n\n"
            "## Critérios de Aceite (DoD)\n\n- [ ] ...\n\n"
            "## Out of Scope\n\n- ...\n",
            encoding="utf-8",
        )
    return str(req_path.relative_to(project_root))


# ---- API pública ------------------------------------------------------------


def new_feature(ws, title: str, language: str = "auto") -> dict[str, Any]:
    pid, root = _require_active(ws)
    st, state_path = _load_state(root)
    fid = _next_feature_id(st, title)
    if fid in st.features:
        raise EhqError(f"feature_id colisão (inesperado): {fid}")
    rel_req = _touch_req_skeleton(root, fid, title)
    st.features[fid] = FeatureState(
        title=title,
        phase="requirements",
        language=language,  # type: ignore[arg-type]
        artifacts=ArtifactPaths(req=rel_req),
    )
    _save_state(state_path, st)
    return {
        "project_id": pid,
        "feature_id": fid,
        "title": title,
        "phase": "requirements",
        "req_file": rel_req,
    }


def show_state(ws, feature_id: str | None = None) -> dict[str, Any]:
    pid, root = _require_active(ws)
    st, _ = _load_state(root)
    payload = st.model_dump(mode="json")
    if feature_id:
        if feature_id not in st.features:
            raise EhqError(
                f"feature inexistente: {feature_id}",
                missing=list(st.features.keys()) or ["(sem features)"],
            )
        payload = {
            "project_id": pid,
            "feature_id": feature_id,
            "feature": payload["features"][feature_id],
        }
    else:
        payload = {"project_id": pid, **payload}
    return payload


def _require_gate_for_phase(st: ProjectState, fid: str, current: Phase) -> None:
    """Autoritarismo: avançar exige gate PASS da fase atual.

    Fase B implementa gates reais; por ora bloqueamos avanço de qualquer fase
    gateada (todas exceto a transição trivial quando nao houver gate ainda).
    """
    gates_by_phase = {
        "requirements": "ears",
        "bdd": "gherkin",
        "tests": "aaa",
        "implementation": "redgreen",
        "refactor": "refactor",
        "review": "gate_all",
    }
    gate = gates_by_phase.get(current)
    if not gate:
        return  # review->done não tem gate próprio além de gate_all já na review
    last = next((g for g in reversed(st.features[fid].gates) if g.name == gate), None)
    if not last or last.status != "pass":
        raise EhqError(
            f"gate '{gate}' da fase atual não passou",
            current_phase=current,
            required_phase=current,  # ainda precisa concluir a fase atual
            missing=[f"rode `ehq gate {gate} --feature {fid}`"],
        )


def advance_feature(ws, feature_id: str) -> dict[str, Any]:
    pid, root = _require_active(ws)
    st, state_path = _load_state(root)
    if feature_id not in st.features:
        raise EhqError(
            f"feature inexistente: {feature_id}",
            missing=list(st.features.keys()) or ["(sem features)"],
        )
    fs = st.features[feature_id]
    current = fs.phase
    if current == "done":
        raise EhqError("feature já concluída (done)", current_phase="done")
    _require_gate_for_phase(st, feature_id, current)
    idx = _PHASES.index(current)
    nxt = _PHASES[idx + 1]
    fs.phase = nxt
    fs.transition_log.append(
        TransitionRecord.model_validate({"from": current, "to": nxt, "gate": None, "by": "orchestrator"})
    )
    from datetime import datetime

    fs.updated_at = datetime.now().astimezone()
    _save_state(state_path, st)
    return {
        "project_id": pid,
        "feature_id": feature_id,
        "from": current,
        "to": nxt,
    }


def regress_feature(
    ws,
    feature_id: str,
    *,
    to: str,
    diagnose: dict | None = None,
) -> dict[str, Any]:
    pid, root = _require_active(ws)
    st, state_path = _load_state(root)
    if feature_id not in st.features:
        raise EhqError(f"feature inexistente: {feature_id}")
    if to not in _PHASES:
        raise EhqError(f"fase destino inválida: {to}")
    fs = st.features[feature_id]
    current = fs.phase
    if _PHASES.index(to) >= _PHASES.index(current):
        raise EhqError(
            f"regressão inválida: destino '{to}' deve preceder fase atual '{current}'",
            current_phase=current,
            required_phase=to,
        )
    fs.phase = to  # type: ignore[assignment]
    fs.transition_log.append(
        TransitionRecord.model_validate(
            {"from": current, "to": to, "by": "diagnostic", "diagnose": diagnose or {}}
        )
    )
    from datetime import datetime

    fs.updated_at = datetime.now().astimezone()
    _save_state(state_path, st)
    return {
        "project_id": pid,
        "feature_id": feature_id,
        "from": current,
        "to": to,
        "diagnose": diagnose,
    }
