import { tool } from "@opencode-ai/plugin"

function ehqProject(): string {
  return process.env.EHQ_PROJECT ?? `${process.env.HOME}/work/harness-opencode`
}

export default tool({
  description:
    "Gestão do state.json por projeto (features e fases do ciclo EARS→BDD→TDD). " +
    "Sempre opera sobre o projeto ATIVO do workspace. Recusas vêm em JSON com exit 2. " +
    "Comandos: new (cria feature em 'requirements'), show (dump do estado ou de uma feature), " +
    "advance (exige gate PASS da fase atual), regress (retorna a fase anterior; exige diagnose).",
  args: {
    cmd: tool.schema
      .enum(["new", "show", "advance", "regress"])
      .describe("Subcomando do state."),
    title: tool.schema
      .string()
      .optional()
      .describe("Título da feature (somente new)."),
    feature_id: tool.schema
      .string()
      .optional()
      .describe("ID da feature (FT-xxxx-...); exigido por advance/regress; opcional em show."),
    language: tool.schema
      .enum(["python", "java", "rust", "auto"])
      .optional()
      .describe("Linguagem-alvo (somente new; default auto)."),
    to: tool.schema
      .enum(["requirements", "bdd", "tests", "implementation", "refactor", "review", "done"])
      .optional()
      .describe("Fase destino (somente regress; deve preceder a fase atual)."),
    diagnose: tool.schema
      .string()
      .optional()
      .describe("JSON de diagnóstico (somente regress): {fase_destino, justificativa, evidencias[], exemplos[]}."),
  },
  async execute(args) {
    const parts: string[] = ["state", args.cmd]
    switch (args.cmd) {
      case "new": {
        if (!args.title) return "Erro: new exige 'title'."
        parts.push(args.title)
        if (args.language) parts.push("--lang", args.language)
        break
      }
      case "show": {
        if (args.feature_id) parts.push(args.feature_id)
        break
      }
      case "advance": {
        if (!args.feature_id) return "Erro: advance exige 'feature_id'."
        parts.push(args.feature_id)
        break
      }
      case "regress": {
        if (!args.feature_id) return "Erro: regress exige 'feature_id'."
        if (!args.to) return "Erro: regress exige 'to'."
        parts.push(args.feature_id, "--to", args.to)
        if (args.diagnose) {
          const file = `${process.env.HOME}/.config/engineer-hq/.last-diagnose.json`
          await Bun.write(file, args.diagnose)
          parts.push("--diagnose", file)
        }
        break
      }
      default:
        return `Erro: cmd desconhecido '${args.cmd}'.`
    }
    try {
      const result = await Bun.$`uv run --project ${ehqProject()} ehq ${parts}`.text()
      return result.trim()
    } catch (e: any) {
      // exit 2 da CLI vem aqui; repassa stderr (JSON estruturado)
      const err = e?.stderr?.toString?.() ?? String(e)
      return `Comando recusado pela CLI ehq:\n${err.trim()}`
    }
  },
})
