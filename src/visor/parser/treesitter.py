"""
Tree-sitter AST Parser for V.I.S.O.R.
Deterministically extracts classes, methods, and import edges from source files.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import tree_sitter
import tree_sitter_python
import tree_sitter_typescript
import tree_sitter_javascript

# ---------------------------------------------------------------------------
# Language setup
# ---------------------------------------------------------------------------

_LANG_PYTHON     = tree_sitter.Language(tree_sitter_python.language())
_LANG_TYPESCRIPT = tree_sitter.Language(tree_sitter_typescript.language_typescript())
_LANG_TSX        = tree_sitter.Language(tree_sitter_typescript.language_tsx())
_LANG_JS         = tree_sitter.Language(tree_sitter_javascript.language())

_EXT_MAP = {
    ".py":  _LANG_PYTHON,
    ".ts":  _LANG_TYPESCRIPT,
    ".tsx": _LANG_TSX,
    ".js":  _LANG_JS,
    ".jsx": _LANG_JS,
}

# ---------------------------------------------------------------------------
# Tree-sitter S-expression queries per language
# ---------------------------------------------------------------------------

_QUERIES = {
    _LANG_PYTHON: {
        "function": "(function_definition name: (identifier) @name) @node",
        "class":    "(class_definition name: (identifier) @name) @node",
        "import":   "(import_from module_name: (dotted_name) @module) @node",
    },
    _LANG_TYPESCRIPT: {
        "function": "(function_declaration name: (identifier) @name) @node",
        "class":    "(class_declaration name: (type_identifier) @name) @node",
        "import":   "(import_statement source: (string) @module) @node",
    },
    _LANG_TSX: {
        "function": "(function_declaration name: (identifier) @name) @node",
        "class":    "(class_declaration name: (type_identifier) @name) @node",
        "import":   "(import_statement source: (string) @module) @node",
    },
    _LANG_JS: {
        "function": "(function_declaration name: (identifier) @name) @node",
        "class":    "(class_declaration name: (identifier) @name) @node",
        "import":   "(import_statement source: (string) @module) @node",
    },
}

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ASTNode:
    file_path: str
    node_type: str         # "function" | "class" | "import"
    name: str
    start_line: int
    end_line: int
    docstring: str = ""

@dataclass
class ParseResult:
    file_path: str
    nodes: List[ASTNode] = field(default_factory=list)
    error: Optional[str] = None

# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

class ASTParser:
    def __init__(self):
        self._parsers: dict[tree_sitter.Language, tree_sitter.Parser] = {}

    def _get_parser(self, lang: tree_sitter.Language) -> tree_sitter.Parser:
        if lang not in self._parsers:
            self._parsers[lang] = tree_sitter.Parser(lang)
        return self._parsers[lang]

    def parse_file(self, file_path: str) -> ParseResult:
        path = Path(file_path)
        lang = _EXT_MAP.get(path.suffix.lower())
        if lang is None:
            return ParseResult(file_path=file_path, error=f"Unsupported file extension: {path.suffix}")

        try:
            source = path.read_bytes()
        except (OSError, IOError) as e:
            return ParseResult(file_path=file_path, error=str(e))

        parser = self._get_parser(lang)
        tree = parser.parse(source)

        nodes: List[ASTNode] = []
        queries = _QUERIES[lang]

        for node_type, query_str in queries.items():
            try:
                q = tree_sitter.Query(lang, query_str)
                cursor = tree_sitter.QueryCursor(q)
                for match in cursor.matches(tree.root_node):
                    captures = match[1]
                    # "name" capture holds the identifier, "node" is the full definition
                    name_nodes = captures.get("name", [])
                    if not name_nodes:
                        continue
                    name_node = name_nodes[0] if isinstance(name_nodes, list) else name_nodes

                    outer_nodes = captures.get("node", [])
                    outer_node = (outer_nodes[0] if isinstance(outer_nodes, list) else outer_nodes) if outer_nodes else name_node

                    name_text = name_node.text.decode("utf-8", errors="replace") if name_node.text else ""
                    # Strip quotes for import module names
                    if node_type == "import":
                        name_text = name_text.strip("'\"")

                    docstring = self._extract_docstring(outer_node, source, lang)

                    nodes.append(ASTNode(
                        file_path=str(file_path),
                        node_type=node_type,
                        name=name_text,
                        start_line=outer_node.start_point[0] + 1,
                        end_line=outer_node.end_point[0] + 1,
                        docstring=docstring,
                    ))
            except Exception:
                pass  # Silently skip malformed queries for non-primary langs

        return ParseResult(file_path=str(file_path), nodes=nodes)

    def _extract_docstring(self, node, source: bytes, lang: tree_sitter.Language) -> str:
        """Extract the first string literal child of a function/class as its docstring (Python style)."""
        if lang != _LANG_PYTHON:
            return ""
        try:
            body = next((c for c in node.children if c.type == "block"), None)
            if not body:
                return ""
            first_stmt = next((c for c in body.children if c.type == "expression_statement"), None)
            if not first_stmt:
                return ""
            string_node = next((c for c in first_stmt.children if c.type == "string"), None)
            if string_node and string_node.text:
                return string_node.text.decode("utf-8", errors="replace").strip("'\"")
        except Exception:
            pass
        return ""


# Singleton to avoid repeated parser construction
ast_parser = ASTParser()
