"""Entrypoint da CLI ehq.

Dispatcher Typer. Subgrupos (project, workspace, front, state, gate) são
adicionados aqui conforme cada fase do roadmap. Cada subgrupo é responsável
por seu próprio esquema de args e validações; este arquivo só orquestra.

Contrato: a CLI emite JSON estruturado por padrão (consumível por custom tools
do opencode); `--human` produz saída amigável. Recusas determinísticas usam
exit code 2 com JSON contendo error, current_phase, required_phase, missing.
"""
from __future__ import annotations

import json
import sys
from typing import Annotated, Optional

import typer

from . import __version__

app = typer.Typer(
    name="ehq",
    help="Harness de engenharia de código: EARS→BDD→TDD com gates mensuráveis.",
    no_args_is_help=True,
    add_completion=False,
   rich_markup_mode="rich",
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"engineer-hq {__version__}")
        raise typer.Exit(code=0)


@app.callback()
def _main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """engineer-hq (ehq) — harness de engenharia de código."""
    # callback apenas registra --version; subcomandos fazem o trabalho
    return None


@app.command()
def doctor() -> None:
    """Diagnóstico do ambiente: paths, versão, configs encontradas.

    Útil no primeiro uso para confirmar que workspace.toml/estado estão
    acessíveis. Saída JSON por padrão; --human para tabela.
    """
    info = {
        "version": __version__,
        "python": sys.version.split()[0],
        "workspace_config": "~/.config/engineer-hq/workspace.toml",
        "workspace_exists": False,  # placeholder; Fase A.3 torna real
        "roadmap": "~/.config/engineer-hq/ROADMAP.md",
    }
    typer.echo(json.dumps(info, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
