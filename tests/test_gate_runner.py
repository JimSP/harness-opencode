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


# ---- gherkin integration ----

_VALID_FEATURE = """\
# language: pt
Funcionalidade: Login

  @req:{fid}
  Cenário: credenciais válidas
    Dado um usuário cadastrado
    Quando submete credenciais válidas
    Então emite token JWT

  @req:{fid}
  Esquema do Cenário: borda 401
    Dado um usuário com <n> tentativas
    Quando submete senha inválida
    Então retorna 401
    Exemplos:
      | n |
      | 1 |
      | 3 |
"""


def _make_feature_at_bdd(tmp_path, monkeypatch, title="X") -> tuple[Path, str]:
    """Cria feature em requirements, injeta gate ears PASS, avança para bdd."""
    projdir, fid = _make_feature(tmp_path, monkeypatch, title)
    # escreve .req.md válido
    req = projdir / ".engineer-hq" / "specs" / f"{fid}.req.md"
    req.write_text(
        f"# {title}\n\n## Requisito\n\nO sistema deve emitir token JWT.\n\n"
        f"## Critérios de Aceite (DoD)\n\n- [ ] exp presente\n",
        encoding="utf-8",
    )
    ws = ws_mod.load_workspace()
    gate_runner.run_gate(ws, gate_name="ears", feature_id=fid)
    state_mod.advance_feature(ws, fid)  # -> bdd
    return projdir, fid


def test_gate_gherkin_fail_sem_artifact(tmp_path, monkeypatch) -> None:
    _, fid = _make_feature_at_bdd(tmp_path, monkeypatch, "Login")
    ws = ws_mod.load_workspace()
    r = gate_runner.run_gate(ws, gate_name="gherkin", feature_id=fid)
    assert r["status"] == "fail"
    assert any(i["code"] == "GHERKIN_NO_FEATURE_ARTIFACT" for i in r["issues"])


def test_gate_gherkin_pass_advance_tests(tmp_path, monkeypatch) -> None:
    projdir, fid = _make_feature_at_bdd(tmp_path, monkeypatch, "Login")
    feat = projdir / ".engineer-hq" / "specs" / f"{fid}.feature"
    feat.write_text(_VALID_FEATURE.format(fid=fid), encoding="utf-8")
    rel = f".engineer-hq/specs/{fid}.feature"
    ws = ws_mod.load_workspace()
    state_mod.set_artifact(ws, fid, kind="feature", path=rel)
    r = gate_runner.run_gate(ws, gate_name="gherkin", feature_id=fid)
    assert r["status"] == "pass"
    assert r["next_phase_hint"] == "tests"
    # advance deve funcionar agora
    out = state_mod.advance_feature(ws, fid)
    assert out["to"] == "tests"


def test_gate_gherkin_fail_no_req_tag(tmp_path, monkeypatch) -> None:
    projdir, fid = _make_feature_at_bdd(tmp_path, monkeypatch, "Login")
    feat = projdir / ".engineer-hq" / "specs" / f"{fid}.feature"
    feat.write_text(
        "# language: pt\nFuncionalidade: Login\n  Cenário: x\n    Dado a\n    Quando b\n    Então c\n",
        encoding="utf-8",
    )
    rel = f".engineer-hq/specs/{fid}.feature"
    ws = ws_mod.load_workspace()
    state_mod.set_artifact(ws, fid, kind="feature", path=rel)
    r = gate_runner.run_gate(ws, gate_name="gherkin", feature_id=fid, persist=False)
    assert r["status"] == "fail"
    assert any(i["code"] == "GHERKIN_NO_REQ_REF" for i in r["issues"])


def test_set_artifact_invalid_kind(tmp_path, monkeypatch) -> None:
    _, fid = _make_feature(tmp_path, monkeypatch, "X")
    ws = ws_mod.load_workspace()
    with pytest.raises(EhqError):
        state_mod.set_artifact(ws, fid, kind="notexist", path="x.py")


def test_set_artifact_test_adds_to_list(tmp_path, monkeypatch) -> None:
    projdir, fid = _make_feature(tmp_path, monkeypatch, "X")
    ws = ws_mod.load_workspace()
    state_mod.set_artifact(ws, fid, kind="test", path="tests/test_x.py")
    state_mod.set_artifact(ws, fid, kind="test", path="tests/test_y.py")
    # dedup
    state_mod.set_artifact(ws, fid, kind="test", path="tests/test_x.py")
    state = json.loads((projdir / ".engineer-hq" / "state.json").read_text())
    assert state["features"][fid]["artifacts"]["tests"] == ["tests/test_x.py", "tests/test_y.py"]
