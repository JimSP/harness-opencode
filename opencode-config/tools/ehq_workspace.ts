import { tool } from "@opencode-ai/plugin"

function ehqProject(): string {
  return process.env.EHQ_PROJECT ?? `${process.env.HOME}/work/harness-opencode`
}

export default tool({
  description:
    "Visão agregada do workspace engineer-hq e gestão de projetos ativos. " +
    "Use quando precisar saber 'onde estou / quais projetos existem / qual ativo'. " +
    "Comandos: status (visão consolidada), project-list, project-info (default: ativo), " +
    "project-use (seleciona ativo), project-add (registra novo projeto no path).",
  args: {
    cmd: tool.schema
      .enum(["status", "project-list", "project-info", "project-use", "project-add"])
      .describe("Subcomando do workspace."),
    project_id: tool.schema
      .string()
      .optional()
      .describe("ID do projeto (PRJ-xxxx-...) para project-use/projet-info; omitido usa o ativo."),
    path: tool.schema
      .string()
      .optional()
      .describe("Path absoluto do projeto-alvo (somente project-add)."),
    name: tool.schema
      .string()
      .optional()
      .describe("Nome amigável do projeto (somente project-add)."),
    language: tool.schema
      .enum(["python", "java", "rust", "auto"])
      .optional()
      .describe("Linguagem do projeto (somente project-add; default auto)."),
    profile: tool.schema
      .enum(["strict", "relaxed", "legacy"])
      .optional()
      .describe("Perfil de gates (somente project-add; default strict)."),
  },
  async execute(args) {
    const parts = []
    switch (args.cmd) {
      case "status":
        parts.push("workspace", "status")
        break
      case "project-list":
        parts.push("project", "list", "--human")
        break
      case "project-info":
        parts.push("project", "info")
        if (args.project_id) parts.push(args.project_id)
        break
      case "project-use":
        if (!args.project_id) {
          return "Erro: project-use exige 'project_id'."
        }
        parts.push("project", "use", args.project_id)
        break
      case "project-add":
        if (!args.path) {
          return "Erro: project-add exige 'path'."
        }
        parts.push("project", "add", "--path", args.path)
        if (args.name) parts.push("--name", args.name)
        if (args.language) parts.push("--lang", args.language)
        if (args.profile) parts.push("--profile", args.profile)
        break
      default:
        return `Erro: cmd desconhecido '${args.cmd}'.`
    }
    try {
      const result = await Bun.$`uv run --project ${ehqProject()} ehq ${parts}`.text()
      return result.trim()
    } catch (e: any) {
      const err = e?.stderr?.toString?.() ?? String(e)
      return `Comando recusado pela CLI ehq:\n${err.trim()}`
    }
  },
})
