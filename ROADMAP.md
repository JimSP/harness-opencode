# Engineer-HQ — Roadmap Vivo

> Documento-fonte único. Qualquer sessão de trabalho (humano ou agente) lê este
> arquivo _antes_ de continuar. Edita aqui ao concluir/ajustar; nunca duplica em
> outros locais. Seção [Status Atual] é a fonte da verdade de progresso.

- **Mantenedor**: Alexandre
- **Repo**: https://github.com/JimSP/harness-opencode
- **Path local**: ~/work/harness-opencode (clone do repo acima)
- **Início**: 2026-07-31
- **Última revisão**: 2026-07-31 (repo criado)
- **Padrão de data**: ISO-8601 UTC

---

## 1. Por que (Why)

Engenheiros lidam com múltiplas frentes (projetos, features, pesquisas, spikes,
reviews externos). Ferramentas de IA assistida (como este opencode) não têm
noção de contexto de trabalho nem governança de fluxo — elas operam
_adiacentemente_ ao código, sem impor ordem, sem exigir requisitos claros, sem
medir se o trabalho terminou de fato.

 engineer-hq resolve três ausências concretas:

1. **Contexto de trabalho** — organizar o que existe (projetos, features,
   frentes) para que o agente saiba "onde está" e "o que falta".
2. **Fluxo autoritativo** — impor EARS → BDD → TDD com gates mensuráveis, em 7
   fases, com retrocesso diagnosticado. O modelo não pula fases porque a CLI
   recusa; não declara "pronto" se os gates não passam.
3. **Métricas de engenharia** — cobertura, mutação, complexidade, SCA, secrets
   — mensuradas por linguagem, derivadas de um único config por projeto, sem
   "salada" de arquivos nativos espalhados.

Tudo em Python/Java/Rust com máxima profundidade. Instalável globalmente. Sem
acoplar o harness ao repositório-alvo (config versionável dentro de cada repo).

## 2. Para Quem (Para Quem)

- **Engenheiro solo** com múltiplos projetos/frentes querendo assistência de IA
  governada por padrões reais.
- **Futuro**: equipes que compartilham perfis e gates via commit do
  `.engineer-hq.toml` (não escopo atual, mas arquitetura não impede).

## 3. O Que (Escopo)

### 3.1 Dentro do plano (IN-SCOPE)

- CLI `ehq` (Python, empacotada via `uv tool`) que orquestra ferramentas de
  engenharia e mantém estado de ciclo de desenvolvimento.
- Camada de contexto: workspace → projeto → feature; + frentes não-feature
  (research/spike/review).
- Máquina de estados de 7 fases por feature com gates autoritativos.
- 6 agents opencode (1 primário + 5 subagents) que cooperam no fluxo.
- Rules `AGENTS.md` declarando contrato conhecido a priori pelo modelo.
- Custom tools opencode (TS) que invocam a CLI e devolvem JSON ao modelo.
- Backend tooling multi-lang (Python/Java/Rust) para lint/format/complexidade/
  cobertura/mutation/SCA/secrets — conforme tabela §7.
- Scaffolding de projetos via Copier (Python/Java/Rust starters).

### 3.2 Fora do plano (OUT-OF-SCOPE)

- Suporte a mais de 3 linguagens no MVP (Python/Java/Rust). Extensões posteriores.
- IDE plugins, integrações CI externas (GitHub Actions/GitLab) — só CLI local.
- Camada de épico (decidido: hierarquia Workspace→Projeto→Feature, sem épico).
- UI gráfica; apenas CLI + saída JSON/markdown ao terminal/opencode.
- Substituir agentes nativos (`build`, `plan`, `general`); coexistem.
- Enforcement por hooks nativos do opencode (inexistem); via CLI+permissões.
- Multi-tenant/equipe (perfis/gates compartilhados só via commit futuro).

## 4. Limites Estabelecidos (Não-Negociáveis)

| Limite | Decisão | Razão |
|---|---|---|
| Autoritarismo | CLI recusa deterministicamente | Única fonte da verdade |
| Estado | `.engineer-hq/state.json` **por projeto**, versionado | Auditação via PR |
| Config de gates | `.engineer-hq.toml` por projeto + perfis | Override local |
| Índice workspace | `~/.config/engineer-hq/workspace.toml`, pessoal | Não-commitado |
| Orquestração | agent primário `ehq-flow` coexiste com `build`, alternado via Tab | Não captura default |
| Máq. estados | 7 fases explícitas com `refactor` e `review` | Fidelidade TDD/CD |
| Diagnóstico | agent `ehq-diag` dedicado; orquestrador executa retorno | Separation of concerns |
| Artefatos | `.engineer-hq/specs/<feature>.req.md` + `.feature` | Rastreabilidade requisito↔teste↔impl |
| TDD interno | Red→Green→Refactor com gate em cada sub-ciclo; `steps` limitado | Evita espiral de custo |
| Coexistência | `ehq-flow` respeita `state.json`; sair para `build` não perde estado | Reentrância |

## 5. Arquitetura (Visão Geral)

```
┌───────────────────────────────────────────────────────────────────┐
│  opencode (TUI/CLI)                                               │
│   ├─ AGENTS.md                     (rules; contrato do fluxo)      │
│   ├─ agents/*.md                   (6 agents .md)                  │
│   └─ tools/*.ts                    (custom tools → Bun.$ ehq ...)  │
└────────────┬──────────────────────────────────────────────────────┘
             │ invoca CLI
             ▼
┌───────────────────────────────────────────────────────────────────┐
│  CLI ehq (Python; instalado global por uv tool)                    │
│   ├─ contexto:  project / workspace / front                       │
│   ├─ estado:    state new/show/advance/regress                    │
│   ├─ gates:     gate <nome> / gate all                            │
│   └─ runners:   lint/format/complexity/coverage/mutation/sca/sec  │
└────────────┬──────────────────────────────────────────────────────┘
             │ subprocess
             ▼
┌───────────────────────────────────────────────────────────────────┐
│  Backends externos (multi-lang)                                   │
│   Python: ruff, pylint, radon, coverage.py, mutmut, bandit, ...   │
│   Java:   checkstyle, pmd, spotbugs, jacoco, pit, find-sec-bugs   │
│   Rust:   clippy, rustfmt, tarpaulin, cargo-mutants, cargo-audit  │
│   Agnóstico: semgrep, lizard, osv-scanner, cyclonedx, gitleaks    │
└───────────────────────────────────────────────────────────────────┘
```

### 5.1 Hierarquia de contextos

```
Workspace (1 engenheiro)
   └─ workspace.toml global indexa:
       ├─ Projetos (dev; têm repo + .engineer-hq.toml + state.json)
       │     └─ Features (ciclo 7-fases; gates)
       └─ Frentes (research/spike/review; status-only; sem gates)
```

### 5.2 Máquina de estados por feature

```
 requirements ──G:ears──▶ bdd ──G:gherkin──▶ tests ──G:aaa──▶ implementation
                                                                        │
                                                            G:redgreen  │
                                                                        ▼
                       done ◀──G:gate_all── review ◀──G:refactor── refactor
```

Avanços exigem gate PASS; retrocessos só via `ehq-diag` (orquestador aplica).

## 6. Organização de Arquivos (Layout)

### 6.1 No repo `harness-opencode` (https://github.com/JimSP/harness-opencode; clone em `~/work/harness-opencode`)

```
engineer-hq/
├── pyproject.toml                 # uv/pep621; entrypoint: ehq=engineer_hq.cli:main
├── README.md                      # instalação + quickstart
├── ROADMAP.md → ~/.config/engineer-hq/ROADMAP.md  (symlink; source of truth)
├── src/engineer_hq/
│   ├── __init__.py
│   ├── __main__.py                # suporta `python -m engineer_hq`
│   ├── cli.py                     # Typer; dispatcher p/ subcomandos
│   ├── workspace.py               # lê/escreve workspace.toml
│   ├── project.py                 # add/list/use/info; resolve projeto ativo
│   ├── front.py                   # add/set/list frentes
│   ├── state.py                   # state.json (CRUD atômico; transições)
│   ├── gates/
│   │   ├── __init__.py
│   │   ├── base.py                # GateResult dataclass, contrato gate
│   │   ├── ears.py                # parser EARS
│   │   ├── gherkin.py             # parser Gherkin
│   │   ├── aaa.py                 # AST Python/Java/Rust p/ AAA
│   │   ├── redgreen.py            # roda testes; compila; lint novo
│   │   ├── refactor.py            # diff snapshot métricas
│   │   └── all.py                 # gate_all (cobertura+mut+CC+SCA+secrets)
│   ├── runners/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── python.py              # ruff, pylint, radon, coverage, mutmut, bandit
│   │   ├── java.py                # checkstyle, pmd, spotbugs, jacoco, pit
│   │   ├── rust.py                # clippy, rustfmt, tarpaulin, cargo-mutants
│   │   └── shared.py              # semgrep, lizard, osv-scanner, gitleaks, cyclonedx
│   ├── normalize.py               # outputs heterogêneos → schema unificado
│   ├── schema.py                  # dataclasses/Pydantic p/ state, gate results
│   ├── config.py                  # carrega .engineer-hq.toml + perfis
│   └── detect.py                  # detecta linguagem (pyproject/pom/Cargo.toml)
├── templates/                     # copier (py/java/rust starters)
│   ├── python/
│   ├── java/
│   └── rust/
└── tests/
    ├── conftest.py
    ├── test_workspace.py
    ├── test_state.py
    └── gates/test_*.py
```

### 6.2 No `~/.config/opencode/` (config do harness, lado opencode)

```
~/.config/opencode/
├── AGENTS.md                      # append §workflow dogfooding
├── opencode.jsonc                 # já existe; sem mudança obrigatória
├── agents/                        # CRIAR
│   ├── ehq-flow.md                # primário (orquestrador)
│   ├── ehq-req.md                 # subagent: requisitos EARS
│   ├── ehq-bdd.md                 # subagent: Gherkin
│   ├── ehq-test.md                # subagent: testes AAA
│   ├── ehq-tdd.md                 # subagent: impl/refactor
│   └── ehq-diag.md                # subagent: diagnóstico read-only
└── tools/                         # CRIAR
    ├── ehq_workspace.ts           # project use/list + workspace status
    ├── ehq_state.ts               # state new/show/advance/regress
    ├── ehq_gate.ts                # gate <nome> --feature <id>
    ├── ehq_config.ts              # config init/set-profile
    ├── ehq_impl.ts                # atalho ehq impl (ehq-tdd)
    ├── ehq_test_gen.ts            # atalho ehq test-gen (ehq-test)
    ├── ehq_diag.ts                # diag ler gate falho → JSON
    └── ehq_summarize.ts           # summarize --json
```

### 6.3 Em cada projeto-alvo (gerado pelo harness, versionável)

```
<project-root>/
├── .engineer-hq.toml              # perfil + gates + limits
├── .engineer-hq/
│   ├── state.json                 # envelopes {version, project_id, features{}...}
│   ├── specs/
│   │   ├── FT-0001-*.req.md       # EARS + DoD
│   │   ├── FT-0001-*.feature      # Gherkin
│   │   └── ...
│   ├── gen/                       # gitignored; configs natives gerados
│   │   ├── ruff.toml
│   │   ├── .pylintrc
│   │   ├── clippy.toml
│   │   └── ...
│   └── reports/                   # gate outputs brutos; rotativos
└── .gitignore                     # inclui: .engineer-hq/gen/, .engineer-hq/reports/
```

### 6.4 No `~/.config/engineer-hq/` (pessoal, dotfiles)

```
~/.config/engineer-hq/
├── workspace.toml                 # índice workspace (projetos + frentes)
└── ROADMAP.md                     # este arquivo (symlink no repo)
```

## 7. Responsabilidades dos Componentes

### 7.1 CLI `ehq` (subcomandos)

| Grupo | Cmd | Responsabilidade |
|---|---|---|
| contexto | `project add` | registra projeto em `workspace.toml`; gera config/statelocal |
| contexto | `project list` | tabela de projetos |
| contexto | `project use <id>` | seta `active_project`; valida acesso |
| contexto | `project info` | dump consolidado projeto+features+ultimo gate |
| contexto | `front add/set/list` | gestão de frentes não-feature |
| contexto | `workspace status [--md]` | visão agregada (projetos+frentes+features) |
| estado | `state new "titulo"` | cria `feature_id`, esqueleto `.req.md`, fase=requirements |
| estado | `state show [--feature <id>]` | dump JSON do estado |
| estado | `state advance <id>` | `phase=proxima` (recusa se gate atual não PASS) |
| estado | `state regress --to --diagnose` | retorno (valida diagnose JSON) |
| gates | `gate <nome> --feature <id>` | roda um gate; JSON `{status, details, next_phase_hint}` |
| gates | `gate all --feature <id>` | pré-requisito de `done` |
| scaff | `config init [--profile]` | gera `.engineer-hq.toml` |
| scaff | `snapshot` | snapshot métricas p/ `gate.refactor` |
| scaff | `scaffold <lang>` | copier starter |
| relatorio | `summarize [--md]` | relatório consolidado |

**Recusa determinística**: toda violação → `exit 2` + JSON
`{"error":"...","current_phase":"...","required_phase":"...","missing":[...]}`.

### 7.2 Custom tools `opencode`

Cada `.ts` é uma ponte enxuta: define args via Zod, invoca `Bun.$\`ehq <cmd> ...\``,
devolve stdout (JSON) ao modelo. Sem lógica de domínio. Mantêm contratos de
`cmd`/`feature`/`gate` exatamente como em `AGENTS.md`.

### 7.3 Agents `opencode`

| Agent | Mode | Responsabilidade |
|---|---|---|
| `ehq-flow` | primary | Orquestra ciclo; despacha subagents por fase; consome gates; aplica retrocessos de `ehq-diag`. Coexiste com `build` — alternado explicitamente. |
| `ehq-req` | subagent | Escreve `.req.md` em EARS + DoD a partir do briefing. |
| `ehq-bdd` | subagent | Converte `.req.md` → `.feature` Gherkin tag `@req:<id>`. |
| `ehq-test` | subagent | Gera `*_test.*` AAA **vermelhos** referenciando `.feature`. |
| `ehq-tdd` | subagent | Ciclos Red→Green→Refactor até gates `redgreen`+`refactor` PASS. Único com edit/bash total. |
| `ehq-diag` | subagent | Read-only; converte falha de gate em JSON `{fase_destino, justificativa, evidencias[], exemplos[]}`. |

### 7.4 Gates (catálogo)

| Gate | Fase | Backend(s) | O que mede | O que bloqueia |
|---|---|---|---|---|
| `ears` | requirements | parser EARS | formato + unambiguous + DoD | avanço a `bdd` |
| `gherkin` | bdd | parser Gherkin | Given/When/Then + tag `@req` | retrocesso a `requirements` |
| `aaa` | tests | AST por linguagem | AAA + Red + ref feature | retrocesso a `bdd` |
| `redgreen` | implementation | pytest/cargo test/mvn test + lint | tests pass + compile + no_new_lint | permanecer em `implementation` |
| `refactor` | refactor | diff snapshot métricas | no regression | retrocesso a `implementation` |
| `gate_all` | review | tudo | cobertura/mut/CC/SCA/secrets | `done` se falha → diag decide |
| `secrets` | review | gitleaks | sem secrets hardcoded | bloqueia `done` |
| `sca` | review | osv-scanner + cyclonedx | sem CVE crítica/alta | bloqueia `done` |
| `secm` | review | bandit/find-sec-bugs/cargo-audit/semgrep | sem misconfig alta | bloqueia `done` |

## 8. Matriz de Permissões por Agent

| Agent | edit | write | bash (globs) | task |
|---|---|---|---|---|
| `build` (default nativo) | (config herdada) | (config herdada) | (config herdada) | — |
| `ehq-flow` | `.engineer-hq/**` allow; demais `ask` | `.engineer-hq/**` allow | `ehq *` allow; `*` ask | `{"*":"deny","ehq-*":"allow"}` |
| `ehq-req` | `.engineer-hq/specs/*.req.md` allow; resto `deny` | `.engineer-hq/specs/*.req.md` allow | `ehq state *` allow; `*` deny | deny |
| `ehq-bdd` | `.engineer-hq/specs/*.feature` allow; resto `deny` | `.engineer-hq/specs/*.feature` allow | `ehq state *` allow; `*` deny | deny |
| `ehq-test` | `tests/**`, `**/test_*.py`, `**/*_test.py`, `**/*Test.java`, `**/test/*.rs` allow; resto `deny` | mesmos paths | `pytest`/`cargo test`/`mvn test`/`gradle test`/`ehq state *` allow; `*` deny | deny |
| `ehq-tdd` | `*` allow | `*` allow | `*` allow | deny |
| `ehq-diag` | `deny` | `deny` | `ehq gate *`/`ehq state show *`/`git diff *`/`git log *` allow; `*` deny | deny |

## 9. Backend Tooling (Refs Conhecidas)

> Confirmação de disponibilidade local (2026-07-31):
> Java 21 + Maven 3.9 OK; brew tem checkstyle/pmd/spotbugs. Rust 1.97 + cargo
> OK; clippy/rustfmt via rustup; cargo-mutants instalável. Faltam: osv-scanner,
> gitleaks, trivy, cargo-tarpaulin, cargo-llvm-cov (todos via `brew`/`cargo`).

| Categoria | Python | Java | Rust | Agnóstico |
|---|---|---|---|---|
| Linter | ruff, pylint | checkstyle, pmd, spotbugs | clippy | semgrep |
| Formatter | ruff format | google-java-format | rustfmt | prettier, shfmt |
| Tipagem | mypy, pyright | javac -Xlint, Error Prone | cargo check, clippy pedantic | — |
| Complexidade | radon (CC/MI/Halstead), mccabe, vulture | pmd CC, crap4java | — | lizard (CC multi-lang) |
| Cobertura | coverage.py | jacoco | tarpaulin, llvm-cov | — |
| Mutação | mutmut | pit | cargo-mutants | — |
| Segurança | bandit | find-sec-bugs | cargo-audit | trivy, gitleaks, semgrep |
| SCA | pip-audit | OWASP dep-check | cargo-audit | osv-scanner, cyclonedx |
| SAST agnóstico | — | — | — | semgrep |
| AST multi-lang | — | — | — | tree-sitter + tree-sitter-languages |
| Agregador | prospector | — | — | — |
| Scaffold | — | — | — | copier (update de projetos) |

## 10. Roadmap Executável

Cada fase = unidade atômica com critérios de aceite (DoD). Atualize [Status
Atual] ao concluir.

### Fase A — Bootstrap CLI + Contexto
**Saída**: CLI `ehq` instalável; `workspace.toml` funcional; 2 custom tools.
- [x] A.1 Repo `~/work/harness-opencode` inicializado; `pyproject.toml` (uv/PEP621); `ehq` entrypoint.
- [x] A.2 `cli.py` (Typer) dispatcher vazio p/ `project`/`workspace`/`state`/`gate`.
- [x] A.3 `workspace.py`: lê/cria `~/.config/engineer-hq/workspace.toml`.
- [x] A.4 `project.py`: `add/list/use/info`; valida path acessível.
- [x] A.5 Geração de `.engineer-hq.toml` + `state.json` vazio no projeto.
- [x] A.6 `workspace status` (visão agregada: projetos + last-gate).
- [x] A.7 Custom tools `ehq_workspace.ts` + `ehq_state.ts` (show). (instalados em ~/.config/opencode/tools/; versionados em opencode-config/tools/; E2E validado via bun)
- [x] A.8 Tests: pytest p/ workspace/project; smoke CLI. (19/19 verdes)

### Fase B — Estado + Gates Básicos (fases 1-3)
**Saída**: ciclo EARS→BDD→tests governado fim-a-fim sem impl.
- [x] B.1 `state.py`: `new/show/advance/regress` (CRUD atômico).
- [x] B.2 `gates/ears.py` (parser EARS).
- [ ] B.3 `gates/gherkin.py`.
- [ ] B.4 `gates/aaa.py` (árbore Python primeiro; Java/Rust depois).
- [x] B.5 `gate` CLI integrando gates + avançando estado. (parcial: gate ears; outros vêm c/ B.3/B.4)
- [x] B.6 `ehq_gate.ts` custom tool.
- [ ] B.7 Tests end-to-end em `examples/python_feature/`.

### Fase C — Agent orquestrador skeleton + Rules
**Saída**: primário `ehq-flow` despachando via placeholders; imposição mostra.
- [ ] C.1 `agents/ehq-flow.md` (mode primary, perms, prompt).
- [ ] C.2 Append §workflow ao `~/.config/opencode/AGENTS.md`.
- [ ] C.3 Validação "alternar via Tab recupera estado".
- [ ] C.4 Demo: usuário descreve feature → `ehq-flow` roda `state new` + gate
  `ears` em placeholder e relata JSON.

### Fase D — Subagents req/bdd/test/tdd/diag + gates redgreen/refactor
**Saída**: ciclo completo até `refactor`.
- [ ] D.1 `agents/ehq-req.md`, `ehq-bdd.md`, `ehq-test.md`, `ehq-tdd.md`, `ehq-diag.md`.
- [ ] D.2 `gates/redgreen.py` (roda pytest/cargo test/mvn test).
- [ ] D.3 `gates/refactor.py` (diff métricas do snapshot).
- [ ] D.4 `state snapshot` (CLI).
- [ ] D.5 `ehq_impl.ts`, `ehq_test_gen.ts`, `ehq_diag.ts`.
- [ ] D.6 E2E: feature 0-passa em 7-fases até `refactor` em projeto Python.

### Fase E — Gate global + ciclo completo de review→done
**Saída**: `done` alcançável só com gates verdes.
- [ ] E.1 `gates/all.py` (coordena runners).
- [ ] E.2 `runners/python.py` (ruff/coverage/mutmut/bandit/radon).
- [ ] E.3 `ehq_summarize.ts` + relatório markdown.
- [ ] E.4 E2E possa chegar a `done` em projeto Python.

### Fase F — Frentes + visão agregada workspace
**Saída**: rastreia pesquisas/spikes/reviews externos; status consolidado.
- [ ] F.1 `front.py` (`add/set/list`); inclusão em `workspace status`.
- [ ] F.2 CLI `ehq front *` testada.
- [ ] F.3 Atualização `AGENTS.md` com instruções front.

### Fase G — Backend tooling multi-lang (Java/Rust)
**Saída**: profundidade máxima nas 3 linguagens.
- [ ] G.1 `runners/java.py` (checkstyle/pmd/spotbugs/jacoco/pit).
- [ ] G.2 `runners/rust.py` (clippy/rustfmt/tarpaulin/cargo-mutants).
- [ ] G.3 `runners/shared.py` (semgrep/lizard/osv-scanner/gitleaks/cyclonedx).
- [ ] G.4 Detecção de linguagem (`detect.py`) e ativação dinâmica de backends.
- [ ] G.5 E2E em projetos Java e Rust de exemplo.

### Fase H — Scaffolding Copier
**Saída**: starters versionados; `ehq scaffold <lang>`.
- [ ] H.1 `templates/python/`, `templates/java/`, `templates/rust/` com
  `.engineer-hq.toml` pré-configurado.
- [ ] H.2 `scaffold.py` integrando `copier.run_copy`.
- [ ] H.3 Update via copier testado.

### Fase Z — Hardening + Docs
- [ ] Z.1 README com quickstart (instalar, `project add`, primeira feature).
- [ ] Z.2 Testes de regressão com projeto-exemplo.
- [ ] Z.3 Documentação dos 6 agents + matriz de perms.
- [ ] Z.4 Patterns de troubleshooting.

## 11. Status Atual

> ÚNICA fonte de verdade de progresso. Atualize a **cada** conclusão de item.

- **Fase atual**: Fase B.3 (gherkin) pendente; A COMPLETA + B.1/B.2/B.5-parcial/B.6 feitos.
- **Decisões técnicas travadas**: §4 desta doc.
- **Documentação opencode confirmada**: custom-tools, agents, rules ✓.
- **Mapeamento de libs**: §9 ✓ (multi-lang, disponibilidade verificada).
- **Testes**: 36/36 verdes (workspace/project/state + gate ears + E2E runner).
- **Custom tools**: 3 TS (workspace, state, gate) instalados e versionados.
- **Fluxo demonstrado**: add→new→gate ears(Fail)→reescreve req→gate ears(Pass)→advance→phase=bdd.
- **Próxima ação sugerida**: B.3 — `gates/gherkin.py` (parser Gherkin + tag @req) p/ fase `bdd`.

## 12. Pontos em Aberto (Decisões Adiadas)

- [x] Path do repo `harness-opencode` (resolvido: `~/work/harness-opencode`, repo GitHub JimSP/harness-opencode).
- [ ] Parser Gherkin Python exato (`gherkin-official` vs `cucumber-expressions`).
- [ ] Estratégia de snapshot de métricas para `gate.refactor` (SQLite vs JSON).
- [ ] Modelo LLM default p/ cada agent (default opencode vs per-agent).
- [ ] Versão do copier e pragma update nos templates (semáforo release).

## 13. Convenções para Continuar Entre Sessões

1. **Toda nova sessão lê** este ROADMAP.md primeiro (caminho fixo
   `~/.config/engineer-hq/ROADMAP.md`).
2. **Antes de codar**, confirmar com o usuário qual item do roadmap será feito.
3. **Ao concluir um item**, marcar `[x]` no §10 e atualizar §11.
4. **Mudanças de escopo/decisão** → editar §4 (limites) e/ou §3 (escopo).
5. **Dúvidas novas** vão para §12; resolved inline e removidas adiante.
6. **Commitar** só quando o usuário pedir; ROADMAP.md pode ser commitado como
   dotfile (não código).
7. **Não duplicar** spec em outros arquivos; este é único.
8. **Métrica de progresso** = % de itens `[x]` no §10.

---

> Fim do ROADMAP. Para iniciar o trabalho, leia §10 (Fase A.1), valide §12 A.
