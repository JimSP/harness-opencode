"""Leitura/escrita do workspace.toml (índice pessoal do engenheiro).

A única fonte de canonical para workspace é workspace_config_path().
Operações são atômicas (escrita temporária + rename) para não corromper.
"""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Iterator

import tomli_w

from .schema import (
    EhqError,
    Workspace,
    workspace_config_path,
)

_VERSION = 1


def _bootstrap_empty() -> Workspace:
    return Workspace(version=_VERSION, owner="")


def load_workspace(path: Path | None = None) -> Workspace:
    """Carrega workspace.toml; cria vazio se inexistente (com diretório).

    Nunca lança para ausência — só para conteúdo inválido.
    """
    target = path or workspace_config_path()
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        ws = _bootstrap_empty()
        save_workspace(ws, target)
        return ws
    try:
        with target.open("rb") as fh:
            raw = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise EhqError(
            f"workspace.toml inválido em {target}: {exc}",
        ) from exc
    try:
        return Workspace.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError
        raise EhqError(
            f"workspace.toml não conforme ao schema ({target}): {exc}",
        ) from exc


def _strip_none(obj):
    """Recursivamente remove chaves None (tomli_w não serializa None)."""
    if isinstance(obj, dict):
        return {k: _strip_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_none(v) for v in obj if v is not None]
    return obj


def save_workspace(ws: Workspace, path: Path | None = None) -> None:
    """Persistência atômica."""
    target = path or workspace_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".toml.tmp")
    with tmp.open("wb") as fh:
        tomli_w.dump(_strip_none(ws.model_dump(mode="json")), fh)
    tmp.replace(target)


def ensure_workspace(path: Path | None = None) -> Workspace:
    """Garante existence; útil chaechando em doctor."""
    return load_workspace(path)


def iter_projects(ws: Workspace) -> Iterator[tuple[str, object]]:
    for pid, pref in ws.projects.items():
        yield pid, pref


def set_active_project(ws: Workspace, project_id: str) -> None:
    """Seta active_project; valida existence."""
    if project_id not in ws.projects:
        raise EhqError(
            f"projeto desconhecido: {project_id}",
            missing=list(ws.projects.keys()) or ["(workspace vazio)"],
        )
    if not Path(ws.projects[project_id].path).exists():
        raise EhqError(
            f"path do projeto inacessível: {ws.projects[project_id].path}",
            **{"project_id": project_id},
        )
    ws.active_project = project_id
