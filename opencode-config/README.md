# opencode-config/

Configuração do opencode que acompanha o harness. Estes arquivos **não são
lidos diretamente** daqui pelo opencode — devem ser instalados em
`~/.config/opencode/`. Este diretório é a **fonte versionável** para que o
harness inclua seus custom tools e futuros agents como parte do release.

## Instalação

```bash
# custom tools
cp opencode-config/tools/*.ts ~/.config/opencode/tools/

# (futuro) agents
cp opencode-config/agents/*.md ~/.config/opencode/agents/

# append de rules ao AGENTS.md (interativo — confira antes de colar)
cat opencode-config/AGENTS.workflow.md >> ~/.config/opencode/AGENTS.md
```

## Variáveis de ambiente

- `EHQ_PROJECT` — path do repo `engineer-hq` (default: `$HOME/work/harness-opencode`).
  Defina se clonou em outro local: `export EHQ_PROJECT=/path/to/harness-opencode`.

## Conteúdo

- `tools/ehq_workspace.ts` — visão agregada + gestão de projetos ativos.
- `tools/ehq_state.ts` — gestão do state.json (new/show/advance/regress).
