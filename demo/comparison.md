# What V.I.S.O.R. adds

This page compares capabilities that are present in the implementation. It is not a measured before-and-after of an agent session, and it does not rank Codex, Claude Code, Cursor, or ripgrep.

Native agent search remains the right fallback. The Agent Skill tells the agent to verify V.I.S.O.R. leads against the working tree and to use ordinary inspection when V.I.S.O.R. is missing or unhelpful.

| Capability | In this repository |
| --- | --- |
| Persistent local repository index | `visor index` writes a project graph under `~/.visor/` |
| AST symbol extraction | Tree-sitter in `src/visor/parser/treesitter.py` for nine languages |
| Dependency graph | Import edges queried by `trace`, `impact_analysis`, and context scoring |
| Deterministic terminal interface | `visor doctor`, `index`, `status`, `context`, `trace`, `drift` |
| MCP integration | `uvx visor-mcp` over stdio, 17 tools |
| Agent Skill | `skills/visor-context/SKILL.md` |
| Drift detection | `visor drift` and `get_drift_report` |
| Optional visual HUD | `src/visor/extension`; the server runs without it |
| Offline lexical retrieval | Default `VISOR_RETRIEVAL_MODE=lexical` |

Semantic retrieval is an explicit mode. It is not required for the commands above.

A context response can include an internal estimate of snippet size versus the full text of candidate files. Publish that number only as what one response calculated. Do not treat it as a general reduction in agent token use.
