"""
Tree-sitter AST Parser for V.I.S.O.R.
Deterministically extracts classes, methods, and import edges from source files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import hashlib

import tree_sitter
import tree_sitter_python
import tree_sitter_typescript
import tree_sitter_javascript
import tree_sitter_go
import tree_sitter_rust
import tree_sitter_java
import tree_sitter_c
import tree_sitter_cpp

# ---------------------------------------------------------------------------
# Language setup
# ---------------------------------------------------------------------------

_LANG_PYTHON = tree_sitter.Language(tree_sitter_python.language())
_LANG_TYPESCRIPT = tree_sitter.Language(tree_sitter_typescript.language_typescript())
_LANG_TSX = tree_sitter.Language(tree_sitter_typescript.language_tsx())
_LANG_JS = tree_sitter.Language(tree_sitter_javascript.language())
_LANG_GO = tree_sitter.Language(tree_sitter_go.language())
_LANG_RUST = tree_sitter.Language(tree_sitter_rust.language())
_LANG_JAVA = tree_sitter.Language(tree_sitter_java.language())
_LANG_C = tree_sitter.Language(tree_sitter_c.language())
_LANG_CPP = tree_sitter.Language(tree_sitter_cpp.language())

_EXT_MAP = {
    ".py": _LANG_PYTHON,
    ".ts": _LANG_TYPESCRIPT,
    ".tsx": _LANG_TSX,
    ".js": _LANG_JS,
    ".jsx": _LANG_JS,
    ".go": _LANG_GO,
    ".rs": _LANG_RUST,
    ".java": _LANG_JAVA,
    ".c": _LANG_C,
    ".h": _LANG_C,
    ".cpp": _LANG_CPP,
    ".cc": _LANG_CPP,
    ".cxx": _LANG_CPP,
    ".hpp": _LANG_CPP,
}

# ---------------------------------------------------------------------------
# Tree-sitter S-expression queries per language
# ---------------------------------------------------------------------------

_QUERIES = {
    _LANG_PYTHON: {
        "function": "(function_definition name: (identifier) @name) @node",
        "class": "(class_definition name: (identifier) @name) @node",
        "import": "(import_from module_name: (dotted_name) @module) @node",
    },
    _LANG_TYPESCRIPT: {
        "function": "(function_declaration name: (identifier) @name) @node",
        "class": "(class_declaration name: (type_identifier) @name) @node",
        "import": "(import_statement source: (string) @module) @node",
    },
    _LANG_TSX: {
        "function": "(function_declaration name: (identifier) @name) @node",
        "class": "(class_declaration name: (type_identifier) @name) @node",
        "import": "(import_statement source: (string) @module) @node",
    },
    _LANG_JS: {
        "function": "(function_declaration name: (identifier) @name) @node",
        "class": "(class_declaration name: (identifier) @name) @node",
        "import": "(import_statement source: (string) @module) @node",
    },
    _LANG_GO: {
        "function": "(function_declaration name: (identifier) @name) @node",
        "class": "(type_declaration (type_spec name: (type_identifier) @name)) @node",
        "import": "(import_spec path: (interpreted_string_literal) @module) @node",
    },
    _LANG_RUST: {
        "function": "(function_item name: (identifier) @name) @node",
        "class": "(struct_item name: (type_identifier) @name) @node",
        "import": "(use_declaration argument: (scoped_identifier) @module) @node",
    },
    _LANG_JAVA: {
        "function": "(method_declaration name: (identifier) @name) @node",
        "class": "(class_declaration name: (identifier) @name) @node",
        "import": "(import_declaration) @node",
    },
    _LANG_C: {
        "function": "(function_definition declarator: (function_declarator declarator: (identifier) @name)) @node",
        "class": "(struct_specifier name: (type_identifier) @name) @node",
        "import": "(preproc_include path: (string_literal) @module) @node",
    },
    _LANG_CPP: {
        "function": "(function_definition declarator: (function_declarator declarator: (identifier) @name)) @node",
        "class": "(class_specifier name: (type_identifier) @name) @node",
        "import": "(preproc_include path: (string_literal) @module) @node",
    },
}

# ---------------------------------------------------------------------------
# Call-site queries for CALLS edge extraction (per language)
# These are separate from _QUERIES to avoid polluting nodes with call sites.
# ---------------------------------------------------------------------------

_CALL_QUERIES = {
    _LANG_PYTHON: "(call function: [(identifier) @callee (attribute attribute: (identifier) @callee)]) @call",
    _LANG_TYPESCRIPT: "(call_expression function: [(identifier) @callee (member_expression property: (property_identifier) @callee)]) @call",
    _LANG_TSX: "(call_expression function: [(identifier) @callee (member_expression property: (property_identifier) @callee)]) @call",
    _LANG_JS: "(call_expression function: [(identifier) @callee (member_expression property: (property_identifier) @callee)]) @call",
    _LANG_GO: "(call_expression function: [(identifier) @callee (selector_expression field: (field_identifier) @callee)]) @call",
    _LANG_RUST: "(call_expression function: [(identifier) @callee (field_expression field: (field_identifier) @callee)]) @call",
    _LANG_JAVA: "(method_invocation name: (identifier) @callee) @call",
    _LANG_C: "(call_expression function: (identifier) @callee) @call",
    _LANG_CPP: "(call_expression function: [(identifier) @callee (field_expression field: (field_identifier) @callee)]) @call",
}

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ASTNode:
    file_path: str
    node_type: str  # "function" | "class" | "import"
    name: str
    start_line: int
    end_line: int
    docstring: str = ""


@dataclass
class ParseResult:
    file_path: str
    file_hash: str = ""
    nodes: List[ASTNode] = field(default_factory=list)
    edges: List[dict] = field(default_factory=list)
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
            return ParseResult(
                file_path=file_path, error=f"Unsupported file extension: {path.suffix}"
            )

        try:
            source = path.read_bytes()
            file_hash = hashlib.sha256(source).hexdigest()
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
                        name_nodes = captures.get("module", [])
                    if not name_nodes:
                        continue
                    name_node = (
                        name_nodes[0] if isinstance(name_nodes, list) else name_nodes
                    )

                    outer_nodes = captures.get("node", [])
                    outer_node = (
                        (
                            outer_nodes[0]
                            if isinstance(outer_nodes, list)
                            else outer_nodes
                        )
                        if outer_nodes
                        else name_node
                    )

                    name_text = (
                        name_node.text.decode("utf-8", errors="replace")
                        if name_node.text
                        else ""
                    )
                    # Strip quotes for import module names
                    if node_type == "import":
                        name_text = name_text.strip("'\"")

                    docstring = self._extract_docstring(outer_node, source, lang)

                    nodes.append(
                        ASTNode(
                            file_path=str(file_path),
                            node_type=node_type,
                            name=name_text,
                            start_line=outer_node.start_point[0] + 1,
                            end_line=outer_node.end_point[0] + 1,
                            docstring=docstring,
                        )
                    )
            except Exception:
                pass  # Silently skip malformed queries for non-primary langs

        # --- IMPORTS edges (file → module) ---
        edges = []
        seen_edges: set[tuple] = set()

        for node in nodes:
            if node.node_type == "import":
                key = (str(file_path), node.name, "IMPORTS")
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append(
                        {"from": str(file_path), "to": node.name, "type": "IMPORTS"}
                    )

        # --- CALLS edges (file → called symbol name) ---
        call_query_str = _CALL_QUERIES.get(lang)
        if call_query_str:
            try:
                cq = tree_sitter.Query(lang, call_query_str)
                cc = tree_sitter.QueryCursor(cq)
                for match in cc.matches(tree.root_node):
                    captures = match[1]
                    callee_nodes = captures.get("callee", [])
                    if not callee_nodes:
                        continue
                    cn = (
                        callee_nodes[0]
                        if isinstance(callee_nodes, list)
                        else callee_nodes
                    )
                    callee_name = (
                        cn.text.decode("utf-8", errors="replace") if cn.text else ""
                    )
                    if callee_name and len(callee_name) > 1:
                        key = (str(file_path), callee_name, "CALLS")
                        if key not in seen_edges:
                            seen_edges.add(key)
                            edges.append(
                                {
                                    "from": str(file_path),
                                    "to": callee_name,
                                    "type": "CALLS",
                                }
                            )
            except Exception:
                pass  # Malformed query or unsupported language variant

        return ParseResult(
            file_path=str(file_path), file_hash=file_hash, nodes=nodes, edges=edges
        )

    def _extract_docstring(
        self, node, source: bytes, lang: tree_sitter.Language
    ) -> str:
        """Extract the first string literal child of a function/class as its docstring (Python style)."""
        if lang != _LANG_PYTHON:
            return ""
        try:
            body = next((c for c in node.children if c.type == "block"), None)
            if not body:
                return ""
            first_stmt = next(
                (c for c in body.children if c.type == "expression_statement"), None
            )
            if not first_stmt:
                return ""
            string_node = next(
                (c for c in first_stmt.children if c.type == "string"), None
            )
            if string_node and string_node.text:
                return string_node.text.decode("utf-8", errors="replace").strip("'\"")
        except Exception:
            pass
        return ""


# Singleton to avoid repeated parser construction
ast_parser = ASTParser()
