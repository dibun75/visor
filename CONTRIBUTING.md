# Contributing to V.I.S.O.R.

Thanks for your interest in contributing to V.I.S.O.R.! This guide will help you get started.

## Quick Start

```bash
git clone https://github.com/dibun75/visor.git
cd visor
uv sync --dev
uv run pytest tests/ -v
```

## How to Add a New Language (Most Common Contribution)

Adding a new language is the easiest way to contribute. Each language requires ~15 lines of code.

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
2. Include: `name`, `description`, `content` (instructions), and optional `strategy` (JSON with `intent`, `scoring_bias`, `tool_priority`)
3. Test via `visor context --skill "your-skill" "test query"`

## Development Guidelines

- **Tests are required** for new features
- **Run the linter** before submitting: `uv run ruff check src/visor/`
- **Keep it simple** — V.I.S.O.R. values pragmatic code over clever code
- **One PR per feature** — don't bundle unrelated changes

## PR Checklist

Before submitting a pull request:

- [ ] Tests pass: `uv run pytest tests/ -v`
- [ ] Linter passes: `uv run ruff check src/visor/`
- [ ] Docs updated (if user-facing change)
- [ ] Commit messages are descriptive

## Questions?

Open an issue with the **question** label, or check the [FAQ](docs/FAQ.md).
