import { tool } from "@opencode-ai/plugin"

function ehqProject(): string {
  return process.env.EHQ_PROJECT ?? `${process.env.HOME}/work/harness-opencode`
}

export default tool({
  description:
    "Anexa um artefato (req/feature/test/impl) à feature no state.json. " +
    "Use quando um subagent produzir um arquivo de requisito (.req.md), " +
    "cenário (.feature), teste ou implementação. Para 'test' e 'impl' " +
    "(listas), o path é adicionado com deduplicação. Sempre opera sobre " +
    "o projeto ativo.",
  args: {
    cmd: tool.schema.literal("set-artifact").describe("Comando (atualmente apenas set-artifact)."),
    feature_id: tool.schema.string().describe("ID da feature (FT-xxxx-...)."),
    kind: tool.schema
      .enum(["req", "feature", "test", "impl"])
      .describe("Tipo do artefato."),
    path: tool.schema
      .string()
      .describe("Caminho relativo ao root do projeto (ex: .engineer-hq/specs/FT-0001-x.feature)."),
  },
  async execute(args) {
    const parts = ["state", args.cmd, args.feature_id, "--kind", args.kind, "--path", args.path]
    try {
      const result = await Bun.$`uv run --project ${ehqProject()} ehq ${parts}`.text()
      return result.trim()
    } catch (e: any) {
      const err = e?.stderr?.toString?.() ?? String(e)
      return `Comando recusado pela CLI ehq:\n${err.trim()}`
    }
  },
})
