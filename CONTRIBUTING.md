# Contributing to V.I.S.O.R.

Thanks for your interest in contributing to V.I.S.O.R.! This guide will help you get started.

## Prerequisites

- Git
- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/)
- Node.js and npm only when changing the HUD or the extension

## Contribution workflow

1. Fork the repository.
2. Clone your fork.
3. Create a focused branch.
4. Make one logical change.
5. Add or update tests.
6. Run the checks that match the files you changed.
7. Push the branch to your fork.
8. Open a pull request against `dibun75/visor:main`.

## Before starting

Search existing issues and pull requests first. Open or comment on an issue before a large architectural change. Never put credentials, private source code, or personal data in issues, pull requests, or logs.

## Python checks

```bash
uv sync --dev
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
uv build
```

## HUD checks

Run these when you change `src/visor/hud`:

```bash
cd src/visor/hud
npm ci
npm run lint
npm run build
npx playwright test
```

## Extension checks

Run these when you change `src/visor/extension`:

```bash
cd src/visor/extension
npm ci
npm run check-types
npm run compile
npx --yes @vscode/vsce package --no-dependencies --out /tmp/visor-hud-audit.vsix
```

## How to Add a New Language (Most Common Contribution)

Adding a new language is the easiest way to contribute. Each language needs a grammar dependency, extraction queries, fixtures, and parser tests.

### Step-by-Step

1. **Install the Tree-sitter grammar:**
   ```bash
   uv add tree-sitter-{language}
   ```

2. **Add to `src/visor/parser/treesitter.py`:**
   ```python
   # At the top, add the import
   import tree_sitter_{language}

   # In the Language setup section
   _LANG_{LANGUAGE} = tree_sitter.Language(tree_sitter_{language}.language())

   # In _EXT_MAP
   ".ext": _LANG_{LANGUAGE},

   # In _QUERIES
   _LANG_{LANGUAGE}: {
       "function": "(function_definition name: (identifier) @name) @node",
       "class":    "(class_definition name: (identifier) @name) @node",
       "import":   "(import_statement source: (string) @module) @node",
   },

   # In _CALL_QUERIES
   _LANG_{LANGUAGE}: "(call_expression function: (identifier) @callee) @call",
   ```

   > **Tip:** Use [Tree-sitter Playground](https://tree-sitter.github.io/tree-sitter/playground) to test your S-expression queries against sample code.

3. **Add a test fixture** in `tests/fixtures/{language}/`:
   ```
   tests/fixtures/{language}/sample.{ext}
   ```
   Include at least: 1 function, 1 class/struct, 1 import, and 1 function call.

4. **Add test cases** in `tests/test_treesitter.py`:
   ```python
   class TestLanguageParsing:
       def test_parses_functions(self):
           result = ast_parser.parse_file(_fixture_path("language", "sample.ext"))
           assert result.error is None
           func_names = [n.name for n in result.nodes if n.node_type == "function"]
           assert "expected_function" in func_names

       def test_parses_classes(self):
           result = ast_parser.parse_file(_fixture_path("language", "sample.ext"))
           class_names = [n.name for n in result.nodes if n.node_type == "class"]
           assert "ExpectedClass" in class_names
   ```

5. **Add the dependency** to `pyproject.toml`:
   ```toml
   "tree-sitter-{language}>=0.23.0",
   ```

6. **Update the language table** in `README.md`.

7. **Run tests:**
   ```bash
   uv run pytest tests/test_treesitter.py -v
   ```

## How to Add a New MCP Tool

1. Add the tool function in `src/visor/tools/core.py` inside `register_tools()`
2. Decorate with `@mcp.tool()` and `@track_telemetry`
3. Add tests in `tests/test_tools.py`
4. Document in `docs/MCP_TOOLS.md`

## How to Add a Built-in Skill

1. Add the skill definition in `src/visor/server.py` inside `_seed_default_skills()`
2. Include: `name`, `description`, `content` (instructions), and optional `strategy` (JSON with `intent_override`, `scoring_bias`, and `tool_priority`)
3. Test via `visor context --skill "your-skill" "test query"`

## Pull requests

- Explain what changed and why.
- Link the related issue.
- Include tests.
- Update public documentation when the change affects user-facing behavior.
- Keep unrelated changes out of the pull request.
- Respond to review comments.
- Wait for all checks.

## Security reports

Read [SECURITY.md](SECURITY.md). Suspected vulnerabilities must not be filed as public issues. Use the private report form linked there.

## Community

Participation is covered by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions?

Open an issue with the **question** label, or check the [FAQ](docs/FAQ.md).
