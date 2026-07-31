"""Testes de project.add/use/list/info + geração de artifacts no projeto-alvo."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engineer_hq import workspace as ws_mod
from engineer_hq import project as proj_mod
from engineer_hq.schema import EhqError


def _home(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_add_generates_files_and_activates(tmp_path: Path, monkeypatch) -> None:
    _home(tmp_path, monkeypatch)
    projdir = tmp_path / "myproj"
    projdir.mkdir()
    ws = ws_mod.load_workspace()
    res = proj_mod.add_project(ws, path=str(projdir), name="My", language="python", profile="relaxed")
    assert res.project_id.startswith("PRJ-0001-")
    cfg = projdir / ".engineer-hq.toml"
    state = projdir / ".engineer-hq" / "state.json"
    assert cfg.exists() and state.exists()
    # profile reflected in state
    sj = json.loads(state.read_text())
    assert sj["active_profile"] == "relaxed"
    # diretórios esperados
    for d in ("specs", "gen", "reports"):
        assert (projdir / ".engineer-hq" / d).is_dir()
    # gitignore atualizado
    gi = projdir / ".gitignore"
    assert ".engineer-hq/gen/" in gi.read_text()
    # add tornou ativo
    assert ws.active_project == res.project_id


def test_add_rejects_duplicate_path(tmp_path: Path, monkeypatch) -> None:
    _home(tmp_path, monkeypatch)
    projdir = tmp_path / "dup"
    projdir.mkdir()
    ws = ws_mod.load_workspace()
    proj_mod.add_project(ws, path=str(projdir))
    with pytest.raises(EhqError) as ei:
        proj_mod.add_project(ws, path=str(projdir))
    assert "já registrado" in str(ei.value.error)


def test_use_validates_existing(tmp_path: Path, monkeypatch) -> None:
    _home(tmp_path, monkeypatch)
    ws = ws_mod.load_workspace()
    with pytest.raises(EhqError):
        proj_mod.use_project(ws, "PRJ-0000-x")


def test_info_uses_active_when_no_arg(tmp_path: Path, monkeypatch) -> None:
    _home(tmp_path, monkeypatch)
    projdir = tmp_path / "p"
    projdir.mkdir()
    ws = ws_mod.load_workspace()
    proj_mod.add_project(ws, path=str(projdir), name="P")
    info = proj_mod.project_info(ws)
    assert info["project_id"].startswith("PRJ-0001-")
    assert info["features_count"] == 0


def test_info_errors_without_active(tmp_path: Path, monkeypatch) -> None:
    _home(tmp_path, monkeypatch)
    ws = ws_mod.load_workspace()
    with pytest.raises(EhqError):
        proj_mod.project_info(ws)
