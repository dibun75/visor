"""Tests for the Tree-sitter AST parser across all supported languages."""

import os
import pytest
from visor.parser.treesitter import ast_parser, _EXT_MAP

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture_path(lang_dir: str, filename: str) -> str:
    return os.path.join(FIXTURES_DIR, lang_dir, filename)


class TestSupportedExtensions:
    """Verify that all expected file extensions are registered."""

    def test_python_extensions(self):
        assert ".py" in _EXT_MAP

    def test_typescript_extensions(self):
        assert ".ts" in _EXT_MAP
        assert ".tsx" in _EXT_MAP

    def test_javascript_extensions(self):
        assert ".js" in _EXT_MAP
        assert ".jsx" in _EXT_MAP

    def test_go_extension(self):
        assert ".go" in _EXT_MAP

    def test_rust_extension(self):
        assert ".rs" in _EXT_MAP

    def test_java_extension(self):
        assert ".java" in _EXT_MAP

    def test_c_extensions(self):
        assert ".c" in _EXT_MAP
        assert ".h" in _EXT_MAP

    def test_cpp_extensions(self):
        assert ".cpp" in _EXT_MAP
        assert ".cc" in _EXT_MAP
        assert ".hpp" in _EXT_MAP

    def test_unsupported_extension(self):
        result = ast_parser.parse_file("test.rb")
        assert result.error is not None
        assert "Unsupported" in result.error


class TestGoParsing:
    def test_parses_go_functions(self):
        result = ast_parser.parse_file(_fixture_path("go", "main.go"))
        assert result.error is None
        func_names = [n.name for n in result.nodes if n.node_type == "function"]
        assert "NewServer" in func_names
        assert "handleRequest" in func_names

    def test_parses_go_types(self):
        result = ast_parser.parse_file(_fixture_path("go", "main.go"))
        class_names = [n.name for n in result.nodes if n.node_type == "class"]
        assert "Server" in class_names

    def test_extracts_go_imports(self):
        result = ast_parser.parse_file(_fixture_path("go", "main.go"))
        import_names = [n.name for n in result.nodes if n.node_type == "import"]
        assert len(import_names) > 0


class TestRustParsing:
    def test_parses_rust_functions(self):
        result = ast_parser.parse_file(_fixture_path("rust", "main.rs"))
        assert result.error is None
        func_names = [n.name for n in result.nodes if n.node_type == "function"]
        assert "start_server" in func_names
        assert "parse_args" in func_names

    def test_parses_rust_structs(self):
        result = ast_parser.parse_file(_fixture_path("rust", "main.rs"))
        class_names = [n.name for n in result.nodes if n.node_type == "class"]
        assert "Config" in class_names


class TestJavaParsing:
    def test_parses_java_methods(self):
        result = ast_parser.parse_file(_fixture_path("java", "Server.java"))
        assert result.error is None
        func_names = [n.name for n in result.nodes if n.node_type == "function"]
        assert "start" in func_names
        assert "getRoutes" in func_names

    def test_parses_java_classes(self):
        result = ast_parser.parse_file(_fixture_path("java", "Server.java"))
        class_names = [n.name for n in result.nodes if n.node_type == "class"]
        assert "Server" in class_names


class TestCParsing:
    def test_parses_c_functions(self):
        result = ast_parser.parse_file(_fixture_path("c", "server.c"))
        assert result.error is None
        func_names = [n.name for n in result.nodes if n.node_type == "function"]
        assert "start_server" in func_names
        assert "parse_port" in func_names

    def test_parses_c_structs(self):
        result = ast_parser.parse_file(_fixture_path("c", "server.c"))
        class_names = [n.name for n in result.nodes if n.node_type == "class"]
        assert "Config" in class_names


class TestCppParsing:
    def test_parses_cpp_functions(self):
        result = ast_parser.parse_file(_fixture_path("cpp", "server.cpp"))
        assert result.error is None
        func_names = [n.name for n in result.nodes if n.node_type == "function"]
        assert "handleRequest" in func_names

    def test_parses_cpp_classes(self):
        result = ast_parser.parse_file(_fixture_path("cpp", "server.cpp"))
        class_names = [n.name for n in result.nodes if n.node_type == "class"]
        assert "Server" in class_names


class TestFileHashing:
    """Verify that file hashing works for deduplication."""

    def test_hash_is_generated(self):
        result = ast_parser.parse_file(_fixture_path("go", "main.go"))
        assert result.file_hash
        assert len(result.file_hash) == 64  # SHA-256 hex digest

    def test_same_file_same_hash(self):
        r1 = ast_parser.parse_file(_fixture_path("go", "main.go"))
        r2 = ast_parser.parse_file(_fixture_path("go", "main.go"))
        assert r1.file_hash == r2.file_hash


class TestEdgeExtraction:
    """Verify that IMPORTS and CALLS edges are extracted."""

    def test_imports_edges(self):
        result = ast_parser.parse_file(_fixture_path("go", "main.go"))
        import_edges = [e for e in result.edges if e["type"] == "IMPORTS"]
        assert len(import_edges) > 0

    def test_calls_edges(self):
        result = ast_parser.parse_file(_fixture_path("java", "Server.java"))
        calls_edges = [e for e in result.edges if e["type"] == "CALLS"]
        assert len(calls_edges) > 0
