# engineer-hq

Harness de engenharia de código: orquestre o desenvolvimento de features impondo
EARS→BDD→TDD com gates mensuráveis, governados por estado por-projeto indexado
no workspace do engenheiro.

> **Status**: Pre-Alpha (Fase A — bootstrap CLI). Veja [`ROADMAP.md`](ROADMAP.md)
> para o plano completo, decisões travadas e progresso.

## Instalação (desenvolvimento)

```bash
git clone https://github.com/JimSP/harness-opencode
cd harness-opencode
uv sync --extra test
uv run ehq --help
```

Instalação como ferramenta global (após release):

```bash
uv tool install engineer-hq
```

## Contexto

`engineer-hq` (= CLI `ehq`) opera dentro do [opencode](https://opencode.ai),
expondo custom tools que o agente `ehq-flow` invoca. Documentação de arquitetura,
limites, agentes, gates e roadmap: [`ROADMAP.md`](ROADMAP.md).
