"""Entrypoint da CLI ehq.

Dispatcher Typer. Subgrupos (project, workspace, state, gate) recebem a lógica
de seus respectivos módulos. Este arquivo só orquestra, formata saída e traduz
``EhqError`` em exit 2 + JSON estruturado.

Contrato: a CLI emite JSON estruturado por padrão (consumível por custom tools
do opencode); `--human` produz saída amigável via rich. Recusas
determinísticas usam exit code 2 com JSON error, current_phase, missing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from . import workspace as ws_mod
from . import project as proj_mod
from . import state as state_mod
from . import gate_runner
from .schema import EhqError, roadmap_path, workspace_config_path, project_paths

app = typer.Typer(
    name="ehq",
    help="Harness de engenharia de código: EARS→BDD→TDD com gates mensuráveis.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)

state_app = typer.Typer(help="Gestão do state.json por projeto (features).")
project_app = typer.Typer(help="Gestão de projetos no workspace.")
workspace_app = typer.Typer(help="Visão agregada do workspace.")
gate_app = typer.Typer(help="Executa gates de validação de fase.")

app.add_typer(project_app, name="project")
app.add_typer(workspace_app, name="workspace")
app.add_typer(state_app, name="state")
app.add_typer(gate_app, name="gate")

err_console = Console(stderr=True)
out_console = Console()


# ---- helpers ----------------------------------------------------------------


def _emit(payload: Any, human: bool = False) -> None:
    """Emite JSON por padrão; --human imprime tabela/resumo."""
    if human:
        _emit_human(payload)
        return
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def _emit_human(payload: Any) -> None:
    """Best-effort tabela para listagens; fallback JSON identado."""
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        cols = list(payload[0].keys())
        table = Table(show_lines=False, header_style="bold")
        for c in cols:
            table.add_column(c)
        for row in payload:
            table.add_row(*[str(row.get(c, "")) for c in cols])
        out_console.print(table)
        return
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def _ehq_error_payload(exc: EhqError) -> dict[str, Any]:
    p = {
        "error": exc.error,
        "current_phase": exc.current_phase,
        "required_phase": exc.required_phase,
        "missing": exc.missing,
    }
    p.update({k: v for k, v in exc.extra.items() if k not in p})
    return p


def _handle_error(exc: EhqError) -> None:
    err_console.print_json(data=_ehq_error_payload(exc))
    raise typer.Exit(code=2)


# ---- top-level --------------------------------------------------------------


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
    return None


@app.command()
def doctor() -> None:
    """Diagnóstico do ambiente: paths, versão, configs encontradas."""
    try:
        ws = ws_mod.load_workspace()
    except EhqError as exc:
        _handle_error(exc)
        return
    info = {
        "version": __version__,
        "python": sys.version.split()[0],
        "workspace_config": str(workspace_config_path()),
        "workspace_exists": True,
        "roadmap": str(roadmap_path()),
        "active_project": ws.active_project,
        "projects_count": len(ws.projects),
        "fronts_count": len(ws.fronts),
    }
    _emit(info)


# ---- project ----------------------------------------------------------------


@project_app.command("add")
def project_add(
    path: Annotated[str, typer.Option("--path", "-p", help="Path do projeto (default: cwd).")],
    name: Annotated[Optional[str], typer.Option("--name", "-n")] = None,
    lang: Annotated[str, typer.Option("--lang", "-l")] = "auto",
    profile: Annotated[str, typer.Option("--profile")] = "strict",
) -> None:
    """Registra novo projeto e gera .engineer-hq.toml + state.json."""
    try:
        ws = ws_mod.load_workspace()
        res = proj_mod.add_project(ws, path=path, name=name, language=lang, profile=profile)
    except EhqError as exc:
        _handle_error(exc)
        return
    _emit({"project_id": res.project_id, "path": res.path, "active": True, "created_files": res.created_files})


@project_app.command("list")
def project_list(
    human: Annotated[bool, typer.Option("--human")] = False,
) -> None:
    """Lista projetos do workspace."""
    ws = ws_mod.load_workspace()
    _emit(proj_mod.list_projects(ws), human=human)


@project_app.command("use")
def project_use(project_id: Annotated[str, typer.Argument()]) -> None:
    """Seta projeto ativo."""
    try:
        ws = ws_mod.load_workspace()
        res = proj_mod.use_project(ws, project_id)
    except EhqError as exc:
        _handle_error(exc)
        return
    _emit(res)


@project_app.command("info")
def project_info(
    project_id: Annotated[Optional[str], typer.Argument()] = None,
) -> None:
    """Dump consolidado do projeto (ativo se não informar)."""
    try:
        ws = ws_mod.load_workspace()
        _emit(proj_mod.project_info(ws, project_id))
    except EhqError as exc:
        _handle_error(exc)


# ---- state ------------------------------------------------------------------


@state_app.command("new")
def state_new(
    title: Annotated[str, typer.Argument()],
    lang: Annotated[str, typer.Option("--lang", "-l")] = "auto",
) -> None:
    """Cria nova feature no projeto ativo (fase=requirements)."""
    try:
        ws = ws_mod.load_workspace()
        _emit(state_mod.new_feature(ws, title, language=lang))
    except EhqError as exc:
        _handle_error(exc)


@state_app.command("show")
def state_show(
    feature_id: Annotated[Optional[str], typer.Argument()] = None,
) -> None:
    """Dump do state.json (ou de uma feature específica)."""
    try:
        ws = ws_mod.load_workspace()
        _emit(state_mod.show_state(ws, feature_id))
    except EhqError as exc:
        _handle_error(exc)


@state_app.command("advance")
def state_advance(feature_id: Annotated[str, typer.Argument()]) -> None:
    """Avança feature para próxima fase (exige gate PASS)."""
    try:
        ws = ws_mod.load_workspace()
        _emit(state_mod.advance_feature(ws, feature_id))
    except EhqError as exc:
        _handle_error(exc)


@state_app.command("regress")
def state_regress(
    feature_id: Annotated[str, typer.Argument()],
    to: Annotated[str, typer.Option("--to")],
    diagnose_file: Annotated[Optional[Path], typer.Option("--diagnose")] = None,
) -> None:
    """Retorna feature a fase anterior, com arquivo JSON de diagnose."""
    diagnose: dict | None = None
    if diagnose_file:
        try:
            diagnose = json.loads(diagnose_file.read_text(encoding="utf-8"))
        except Exception as exc:
            _handle_error(EhqError(f"diagnose inválido: {exc}"))
            return
    try:
        ws = ws_mod.load_workspace()
        _emit(state_mod.regress_feature(ws, feature_id, to=to, diagnose=diagnose))
    except EhqError as exc:
        _handle_error(exc)


@state_app.command("set-artifact")
def state_set_artifact(
    feature_id: Annotated[str, typer.Argument()],
    kind: Annotated[str, typer.Option("--kind")],
    path: Annotated[str, typer.Option("--path")],
) -> None:
    """Anexa um artefato (req/feature/test/impl) à feature no state.json."""
    try:
        ws = ws_mod.load_workspace()
        _emit(state_mod.set_artifact(ws, feature_id, kind=kind, path=path))
    except EhqError as exc:
        _handle_error(exc)


# ---- workspace --------------------------------------------------------------


@workspace_app.command("status")
def workspace_status(
    human: Annotated[bool, typer.Option("--human")] = False,
) -> None:
    """Visão agregada do workspace (projetos + frentes)."""
    ws = ws_mod.load_workspace()
    _emit(
        {
            "owner": ws.owner,
            "active_project": ws.active_project,
            "projects": [
                {
                    "project_id": pid,
                    "name": p.name,
                    "language": p.language,
                    "profile": p.profile,
                    "active": ws.active_project == pid,
                    "features_count": _count_features(Path(p.path)),
                    "accessible": Path(p.path).exists(),
                }
                for pid, p in ws.projects.items()
            ],
            "fronts": [
                {
                    "front_id": fid,
                    "kind": f.kind,
                    "title": f.title,
                    "status": f.status,
                    "related_projects": f.related_projects,
                }
                for fid, f in ws.fronts.items()
            ],
        },
        human=human,
    )


def _count_features(project_root: Path) -> int:
    from .schema import project_paths

    state_path = project_paths(project_root)["state"]
    try:
        import json

        return len(json.loads(state_path.read_text(encoding="utf-8")).get("features", {}))
    except Exception:
        return 0


# ---- gate -------------------------------------------------------------------


@gate_app.command("ears")
def gate_ears(feature_id: Annotated[str, typer.Argument()]) -> None:
    """Valida o .req.md da feature no padrão EARS + DoD."""
    try:
        ws = ws_mod.load_workspace()
        _emit(gate_runner.run_gate(ws, gate_name="ears", feature_id=feature_id))
    except EhqError as exc:
        _handle_error(exc)


@gate_app.command("gherkin")
def gate_gherkin(feature_id: Annotated[str, typer.Argument()]) -> None:
    """Valida o .feature da feature (sintaxe + tag @req + outline)."""
    try:
        ws = ws_mod.load_workspace()
        _emit(gate_runner.run_gate(ws, gate_name="gherkin", feature_id=feature_id))
    except EhqError as exc:
        _handle_error(exc)


if __name__ == "__main__":
    app()
