# V.I.S.O.R. Agent Skill

The portable Skill source is [`skills/visor-context/SKILL.md`](../skills/visor-context/SKILL.md).
It is intentionally small: it directs coding agents to verify a compact
V.I.S.O.R. context result and fall back to normal repository inspection.

## Codex

Copy or symlink `skills/visor-context` into a discoverable Codex skills
directory (for example, `~/.codex/skills/visor-context`), then start a new
Codex task in the repository. The metadata lets Codex select the Skill for
repository exploration, debugging, refactoring, and dependency analysis.

## Claude Code

Claude Code can use the same `SKILL.md` content in the project's configured
skills directory. Copy the directory there according to the team's Claude Code
Skill discovery configuration. No product-specific instructions are embedded in
the Skill; it calls the `visor` CLI or an already-configured V.I.S.O.R. MCP
server.

## Generic agents and VS Code clients

Use the body of `SKILL.md` as the repository-context instruction. Configure the
client's MCP entry manually if MCP tools are desired; otherwise the terminal
commands work in a project checkout:

```bash
visor doctor
visor index
visor context "find the relevant authentication flow" --json
```

## Tool-surface measurement

Before adding more MCP tools or making a client-specific integration the
default, record the client-visible tool schema count and serialized definition
size with and without that change. Pair this measurement with the benchmark
protocol in `benchmarks/`; do not infer an agent-context benefit from an
integration being available.
