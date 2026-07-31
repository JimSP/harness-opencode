"""Testes do workspace.toml: criação, idempotência, erro sintaxe."""
from __future__ import annotations

from pathlib import Path

import pytest

from engineer_hq.schema import Workspace
from engineer_hq import workspace as ws_mod


def test_load_creates_empty_when_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    ws = ws_mod.load_workspace()
    assert isinstance(ws, Workspace)
    assert ws.projects == {}
    assert ws.active_project is None
    # arquivo fisicamente criado
    cfg = tmp_path / ".config" / "engineer-hq" / "workspace.toml"
    assert cfg.exists()


def test_load_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    ws1 = ws_mod.load_workspace()
    ws2 = ws_mod.load_workspace()
    assert ws1 == ws2


def test_set_active_project_validates_existence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    ws = ws_mod.load_workspace()
    from engineer_hq.schema import EhqError

    with pytest.raises(EhqError):
        ws_mod.set_active_project(ws, "PRJ-9999-x")


def test_invalid_toml_raises_ehqerror(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = tmp_path / ".config" / "engineer-hq" / "workspace.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("version = ", encoding="utf-8")  # toml inválido
    from engineer_hq.schema import EhqError

    with pytest.raises(EhqError):
        ws_mod.load_workspace()
