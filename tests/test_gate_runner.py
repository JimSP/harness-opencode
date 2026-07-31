"""Testes E2E do gate ears integrado ao state.json via gate_runner."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engineer_hq import workspace as ws_mod
from engineer_hq import project as proj_mod
from engineer_hq import state as state_mod
from engineer_hq import gate_runner
from engineer_hq.schema import EhqError


_VALID_REQ = """\
# Login com senha

> feature: {fid}

## Requisito

Quando o usuário submete credenciais válidas, o sistema deve emitir um token JWT.

## Critérios de Aceite (DoD)

- [ ] Token contém claim exp
- [ ] Status 401 para credenciais inválidas
"""


def _bootstrap(tmp_path: Path, monkeypatch) -> tuple[Path, str]:
    monkeypatch.setenv("HOME", str(tmp_path))
    projdir = tmp_path / "p"
    projdir.mkdir()
    ws = ws_mod.load_workspace()
    proj_mod.add_project(ws, path=str(projdir), name="P", language="python")
    return projdir, ""


def _make_feature(tmp_path, monkeypatch, title="X") -> tuple[Path, str]:
    projdir, _ = _bootstrap(tmp_path, monkeypatch)
    ws = ws_mod.load_workspace()
    res = state_mod.new_feature(ws, title)
    return projdir, res["feature_id"]


def test_gate_ears_skeleton_fails(tmp_path, monkeypatch) -> None:
    projdir, fid = _make_feature(tmp_path, monkeypatch, "Login")
    ws = ws_mod.load_workspace()
    r = gate_runner.run_gate(ws, gate_name="ears", feature_id=fid)
    assert r["status"] == "fail"
    codes = [i["code"] for i in r["issues"]]
    assert "EARS_NO_SENTENCE" in codes


def test_gate_ears_valid_passes_and_advances(tmp_path, monkeypatch) -> None:
    projdir, fid = _make_feature(tmp_path, monkeypatch, "Login")
    req_path = projdir / ".engineer-hq" / "specs" / f"{fid}.req.md"
    req_path.write_text(_VALID_REQ.format(fid=fid), encoding="utf-8")
    ws = ws_mod.load_workspace()
    r = gate_runner.run_gate(ws, gate_name="ears", feature_id=fid)
    assert r["status"] == "pass"
    assert r["next_phase_hint"] == "bdd"
    # gate persistido no state
    state = json.loads((projdir / ".engineer-hq" / "state.json").read_text())
    gates = state["features"][fid]["gates"]
    assert any(g["name"] == "ears" and g["status"] == "pass" for g in gates)
    # advance agora funciona
    out = state_mod.advance_feature(ws, fid)
    assert out["to"] == "bdd"


def test_advance_after_gate_fail_blocks(tmp_path, monkeypatch) -> None:
    _, fid = _make_feature(tmp_path, monkeypatch, "X")
    ws = ws_mod.load_workspace()
    gate_runner.run_gate(ws, gate_name="ears", feature_id=fid)  # fail (skeleton)
    with pytest.raises(EhqError) as ei:
        state_mod.advance_feature(ws, fid)
    assert "gate 'ears'" in str(ei.value.error)


def test_gate_unknown_recusa(tmp_path, monkeypatch) -> None:
    _, fid = _make_feature(tmp_path, monkeypatch, "X")
    ws = ws_mod.load_workspace()
    with pytest.raises(EhqError) as ei:
        gate_runner.run_gate(ws, gate_name="nope", feature_id=fid)
    assert "gate desconhecido" in str(ei.value.error)


def test_gate_requires_active_project(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    ws = ws_mod.load_workspace()  # sem projeto ativo
    with pytest.raises(EhqError):
        gate_runner.run_gate(ws, gate_name="ears", feature_id="FT-0001-x")


def test_gate_unknown_feature_404(tmp_path, monkeypatch) -> None:
    _bootstrap(tmp_path, monkeypatch)
    ws = ws_mod.load_workspace()
    with pytest.raises(EhqError) as ei:
        gate_runner.run_gate(ws, gate_name="ears", feature_id="FT-9999-x")
    assert "feature inexistente" in str(ei.value.error)
