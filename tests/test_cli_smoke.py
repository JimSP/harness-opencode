"""Smoke test da CLI: garante que o entrypoint carrega e responde."""
from __future__ import annotations

import json
from typer.testing import CliRunner

from engineer_hq.cli import app


runner = CliRunner()


def test_version_callback() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "engineer-hq" in result.stdout
    assert result.stdout.strip().split()[-1]  # tem versão


def test_doctor_emits_json() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["version"]
    assert "python" in payload
    assert payload["workspace_config"].endswith("workspace.toml")
    assert payload["workspace_exists"] is False  # ainda não implementado


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code != 0  # no_args_is_help -> código != 0
    assert "Usage:" in result.stdout or "Usage:" in (result.stderr or "")
