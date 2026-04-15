"""
V.I.S.O.R. CLI — Terminal interface for the Context Intelligence Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Usage:
    visor context "how is authentication handled"
    visor fix "login crash on null user"
    visor explain "database client module"
    visor trace src/auth.py src/db/client.py
    visor drift
"""
import argparse
import json
import sys
import os


def _init_workspace():
    """Ensure WORKSPACE_ROOT is set for the engine."""
    if not os.environ.get("WORKSPACE_ROOT"):
        os.environ["WORKSPACE_ROOT"] = os.getcwd()


def _format_output(data: dict, human: bool = True) -> str:
    """Format output as human-readable table or raw JSON."""
    if not human:
        return json.dumps(data, indent=2)
    
    lines = []

    # Header: query + intent + skill
    debug = data.get("debug", {})
    lines.append(f"\n{'='*60}")
    lines.append("  V.I.S.O.R. Context Intelligence Engine")
    lines.append(f"{'='*60}")
    lines.append(f"  Query:  {data.get('query', '?')}")
    lines.append(f"  Intent: {debug.get('intent', '?')}")
    if debug.get("skill"):
        lines.append(f"  Skill:  {debug['skill']}")
    lines.append(f"{'─'*60}")

    # Metrics
    metrics = data.get("metrics", {})
    if metrics:
        without = metrics.get("estimated_tokens_without", 0)
        with_t = metrics.get("estimated_tokens_with", 0)
        reduction = metrics.get("reduction_percent", 0)
        lines.append(f"  Tokens without V.I.S.O.R.: {without:,}")
        lines.append(f"  Tokens with V.I.S.O.R.:    {with_t:,}")
        lines.append(f"  Reduction:                 {reduction}%")
        lines.append(f"{'─'*60}")

    # Context nodes
    context = data.get("context", [])
    if context:
        lines.append(f"  Selected {len(context)} nodes (truncated={data.get('truncated', False)}):")
        lines.append("")
        for node in context:
            nid = str(node.get("id", "?"))
            score = node.get("relevance_score", 0)
            lines.append(f"  [{score:.4f}]  {node.get('file_path', '?')}:{node.get('name', '?')}")
            
            # Reasoning
            reasoning = debug.get("reasoning", {}).get(nid, [])
            for r in reasoning:
                lines.append(f"            → {r}")
            lines.append("")
    else:
        lines.append("  No relevant context found.")
        lines.append("  → V.I.S.O.R. needs to index your workspace first.")
        lines.append("  → Run the MCP server or use the IDE extension to trigger indexing.")

    # Recommended next tools
    rec = data.get("recommended_next", [])
    if rec:
        lines.append(f"  Recommended next: {', '.join(rec)}")

    lines.append(f"{'='*60}\n")
    return "\n".join(lines)


def cmd_context(args):
    """Run build_context with optional skill."""
    _init_workspace()
    from visor.tools.context_engine import build_context
    result = build_context(args.query, skill_name=args.skill)
    print(_format_output(result, human=not args.json))


def cmd_fix(args):
    """Shortcut: build_context with bug-fixer skill."""
    _init_workspace()
    from visor.tools.context_engine import build_context
    result = build_context(args.query, skill_name="bug-fixer")
    print(_format_output(result, human=not args.json))


def cmd_explain(args):
    """Shortcut: build_context with architecture-explainer skill."""
    _init_workspace()
    from visor.tools.context_engine import build_context
    result = build_context(args.query, skill_name="architecture-explainer")
    print(_format_output(result, human=not args.json))


def cmd_trace(args):
    """Trace architectural path between two files."""
    _init_workspace()
    import networkx as nx
    from visor.db.client import db_client

    db_client.conn.commit()
    cursor = db_client.conn.cursor()
    cursor.execute("SELECT from_node, to_node FROM edges")

    G = nx.DiGraph()
    for from_n, to_n in cursor.fetchall():
        G.add_edge(from_n, to_n)

    if not G.has_node(args.source) or not G.has_node(args.target):
        print(json.dumps({"error": "Source or target node not found in graph."}))
        return

    try:
        path = nx.shortest_path(G, source=args.source, target=args.target)
        result = {"source": args.source, "target": args.target, "path": path, "hops": len(path) - 1}
    except nx.NetworkXNoPath:
        result = {"error": "No path found between these nodes."}

    print(json.dumps(result, indent=2))


def cmd_drift(args):
    """Check drift status for all tracked files."""
    _init_workspace()
    from visor.db.client import db_client

    db_client.conn.commit()
    cursor = db_client.conn.cursor()

    try:
        cursor.execute("SELECT file_path, changed_at FROM file_changelog ORDER BY changed_at DESC LIMIT 20")
        rows = cursor.fetchall()
    except Exception:
        rows = []

    if not rows:
        print("No file changes tracked yet. The file watcher may not have started.")
        return

    print(f"\n{'='*60}")
    print("  V.I.S.O.R. Drift Monitor — Recent Changes")
    print(f"{'='*60}")
    for path, changed_at in rows:
        print(f"  {changed_at}  {path}")
    print(f"{'='*60}\n")


def cmd_init(args):
    """Auto-detect IDE and generate MCP config for V.I.S.O.R."""
    import shutil

    visor_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Try to find the visor executable/package path
    visor_bin = shutil.which("visor-mcp")

    mcp_entry = {
        "command": "uv",
        "args": [
            "--directory", visor_path,
            "run", "-q", os.path.join(visor_path, "src", "visor", "server.py"),
        ],
        "env": {}
    }

    # If installed via pip, use the entry point directly
    if visor_bin:
        mcp_entry = {
            "command": "visor-mcp",
            "args": [],
            "env": {}
        }

    # Detect IDE configs
    ide_configs = [
        ("Antigravity", os.path.expanduser("~/.gemini/antigravity/mcp_config.json")),
        ("Cursor", os.path.expanduser("~/.cursor/mcp.json")),
    ]

    config_written = False
    for ide_name, config_path in ide_configs:
        if os.path.exists(os.path.dirname(config_path)):
            # Read existing config or create new
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    try:
                        config = json.load(f)
                    except json.JSONDecodeError:
                        config = {}
            else:
                config = {}

            if "mcpServers" not in config:
                config["mcpServers"] = {}

            if "visor" in config["mcpServers"]:
                print(f"  ✓ {ide_name}: V.I.S.O.R. already configured at {config_path}")
                config_written = True
                continue

            config["mcpServers"]["visor"] = mcp_entry

            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            print(f"  ✓ {ide_name}: Config written to {config_path}")
            config_written = True

    if not config_written:
        # Fallback: print the config for manual setup
        print("  No supported IDE detected. Add this to your MCP config:\n")
        print(json.dumps({"visor": mcp_entry}, indent=2))
        print()

    print(f"\n{'='*60}")
    print("  V.I.S.O.R. is ready!")
    print(f"{'='*60}")
    print("  Next steps:")
    print("    1. Restart your IDE / AI session")
    print("    2. Your AI agent now has access to 16 V.I.S.O.R. tools")
    print("    3. Try: ask your agent to 'use build_context to find auth code'")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        prog="visor",
        description="V.I.S.O.R. — Context Intelligence Engine CLI",
    )
    from visor import __version__
    parser.add_argument("--version", "-v", action="version", version=f"V.I.S.O.R. {__version__}")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # visor init
    p_init = sub.add_parser("init", help="Auto-configure V.I.S.O.R. for your IDE")
    p_init.set_defaults(func=cmd_init)

    # visor context
    p_ctx = sub.add_parser("context", help="Build ranked context for a query")
    p_ctx.add_argument("query", help="Natural language query")
    p_ctx.add_argument("--skill", "-s", default=None, help="Apply a skill strategy")
    p_ctx.add_argument("--json", "-j", action="store_true", help="Output raw JSON")
    p_ctx.set_defaults(func=cmd_context)

    # visor fix
    p_fix = sub.add_parser("fix", help="Find context for a bug (uses bug-fixer skill)")
    p_fix.add_argument("query", help="Bug description")
    p_fix.add_argument("--json", "-j", action="store_true", help="Output raw JSON")
    p_fix.set_defaults(func=cmd_fix)

    # visor explain
    p_exp = sub.add_parser("explain", help="Explain a module (uses architecture-explainer skill)")
    p_exp.add_argument("query", help="What to explain")
    p_exp.add_argument("--json", "-j", action="store_true", help="Output raw JSON")
    p_exp.set_defaults(func=cmd_explain)

    # visor trace
    p_trace = sub.add_parser("trace", help="Trace path between two files")
    p_trace.add_argument("source", help="Source file path")
    p_trace.add_argument("target", help="Target file path")
    p_trace.set_defaults(func=cmd_trace)

    # visor drift
    p_drift = sub.add_parser("drift", help="Show recent file changes (drift detection)")
    p_drift.set_defaults(func=cmd_drift)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()

