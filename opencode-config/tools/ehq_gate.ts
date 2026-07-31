import { tool } from "@opencode-ai/plugin"

function ehqProject(): string {
  return process.env.EHQ_PROJECT ?? `${process.env.HOME}/work/harness-opencode`
}

export default tool({
  description:
    "Executa um gate de validação de fase do ciclo EARS→BDD→TDD. " +
    "Sempre opera sobre o projeto ATIVO e a feature informada. " +
    "Persiste o resultado no state.json (substitui gate anterior de mesmo nome). " +
    "Saída JSON: {name, phase, status, issues[], details, project_id, feature_id, next_phase_hint}. " +
    "Gates disponíveis (fase atual): ears (requirements). Outros virão em fases posteriores.",
  args: {
    gate: tool.schema
      .enum(["ears"])
      .describe("Nome do gate a executar."),
    feature_id: tool.schema
      .string()
      .describe("ID da feature (FT-xxxx-...)."),
  },
  async execute(args) {
    const parts = ["gate", args.gate, args.feature_id]
    try {
      const result = await Bun.$`uv run --project ${ehqProject()} ehq ${parts}`.text()
      return result.trim()
    } catch (e: any) {
      const err = e?.stderr?.toString?.() ?? String(e)
      return `Comando recusado pela CLI ehq:\n${err.trim()}`
    }
  },
})
