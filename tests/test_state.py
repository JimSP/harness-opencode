"""Testes de state.new/show/advance/regress com gates autoritativos."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engineer_hq import workspace as ws_mod
from engineer_hq import project as proj_mod
from engineer_hq import state as state_mod
from engineer_hq.schema import EhqError


def _bootstrap(tmp_path: Path, monkeypatch) -> tuple[Path, str]:
    monkeypatch.setenv("HOME", str(tmp_path))
    projdir = tmp_path / "p"
    projdir.mkdir()
    ws = ws_mod.load_workspace()
    proj_mod.add_project(ws, path=str(projdir), name="P", language="python")
    return projdir, proj_mod.list_projects(ws)[0]["project_id"]


def _state_path(projdir: Path) -> Path:
    return projdir / ".engineer-hq" / "state.json"


def _inject_gate(projdir: Path, fid: str, gate: str, status: str = "pass") -> None:
    p = _state_path(projdir)
    d = json.loads(p.read_text())
    d["features"][fid]["gates"].append(
        {"name": gate, "phase": "requirements", "status": status, "at": "2026-07-31T00:00:00-03:00", "details": {}}
    )
    p.write_text(json.dumps(d, indent=2))


def test_new_feature_creates_state_and_req_skeleton(tmp_path: Path, monkeypatch) -> None:
    projdir, _ = _bootstrap(tmp_path, monkeypatch)
    ws = ws_mod.load_workspace()
    res = state_mod.new_feature(ws, "Login com senha")
    assert res["phase"] == "requirements"
    fid = res["feature_id"]
    assert fid.startswith("FT-0001-")
    req = projdir / ".engineer-hq" / "specs" / f"{fid}.req.md"
    assert req.exists()
    assert "## Requisito" in req.read_text()


def test_advance_blocks_without_gate_pass(tmp_path: Path, monkeypatch) -> None:
    _, _ = _bootstrap(tmp_path, monkeypatch)
    ws = ws_mod.load_workspace()
    res = state_mod.new_feature(ws, "X")
    fid = res["feature_id"]
    with pytest.raises(EhqError) as ei:
        state_mod.advance_feature(ws, fid)
    assert "gate 'ears'" in str(ei.value.error)
    assert ei.value.current_phase == "requirements"


def test_advance_succeeds_after_gate_pass(tmp_path: Path, monkeypatch) -> None:
    projdir, _ = _bootstrap(tmp_path, monkeypatch)
    ws = ws_mod.load_workspace()
    res = state_mod.new_feature(ws, "X")
    fid = res["feature_id"]
    _inject_gate(projdir, fid, "ears", "pass")
    r = state_mod.advance_feature(ws, fid)
    assert r["to"] == "bdd"
    # estado persistido
    sj = json.loads(_state_path(projdir).read_text())
    assert sj["features"][fid]["phase"] == "bdd"
    assert sj["features"][fid]["transition_log"][-1]["to"] == "bdd"


def test_regress_rejects_forward_target(tmp_path: Path, monkeypatch) -> None:
    _, _ = _bootstrap(tmp_path, monkeypatch)
    ws = ws_mod.load_workspace()
    res = state_mod.new_feature(ws, "X")
    fid = res["feature_id"]
    with pytest.raises(EhqError):
        state_mod.regress_feature(ws, fid, to="bdd")  # bdd >= requirements -> recusa


def test_regress_succeeds_when_target_preceeds(tmp_path: Path, monkeypatch) -> None:
    projdir, _ = _bootstrap(tmp_path, monkeypatch)
    ws = ws_mod.load_workspace()
    res = state_mod.new_feature(ws, "X")
    fid = res["feature_id"]
    _inject_gate(projdir, fid, "ears", "pass")
    state_mod.advance_feature(ws, fid)  # requirements -> bdd
    r = state_mod.regress_feature(ws, fid, to="requirements", diagnose={"reason": "Gherkin sem @req"})
    assert r["to"] == "requirements"
    sj = json.loads(_state_path(projdir).read_text())
    assert sj["features"][fid]["transition_log"][-1]["diagnose"]["reason"] == "Gherkin sem @req"


def test_advance_on_done_blocks(tmp_path: Path, monkeypatch) -> None:
    projdir, _ = _bootstrap(tmp_path, monkeypatch)
    ws = ws_mod.load_workspace()
    res = state_mod.new_feature(ws, "X")
    fid = res["feature_id"]
    # força estado done
    p = _state_path(projdir)
    d = json.loads(p.read_text())
    d["features"][fid]["phase"] = "done"
    p.write_text(json.dumps(d, indent=2))
    with pytest.raises(EhqError) as ei:
        state_mod.advance_feature(ws, fid)
    assert "done" in str(ei.value.error).lower()


def test_show_filters_by_feature(tmp_path: Path, monkeypatch) -> None:
    _, _ = _bootstrap(tmp_path, monkeypatch)
    ws = ws_mod.load_workspace()
    res = state_mod.new_feature(ws, "First")
    fid = res["feature_id"]
    out = state_mod.show_state(ws, fid)
    assert out["feature_id"] == fid
    assert "feature" in out
    assert out["feature"]["title"] == "First"
