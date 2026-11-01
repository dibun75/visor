"""Tests for the Tree-sitter AST parser across all supported languages."""

import os
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

    def test_csharp_extension(self):
        assert ".cs" in _EXT_MAP

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


class TestCSharpParsing:
    def test_parses_namespace_and_usings(self):
        result = ast_parser.parse_file(_fixture_path("csharp", "sample.cs"))
        assert result.error is None
        class_names = [n.name for n in result.nodes if n.node_type == "class"]
        import_names = [n.name for n in result.nodes if n.node_type == "import"]
        assert "Demo.App" in class_names
        assert "System" in import_names
        assert "System.Collections.Generic" in import_names
        assert "Demo.Lib" in import_names
        assert "System.Math" in import_names
        assert "Alias" not in import_names

    def test_parses_type_declarations(self):
        result = ast_parser.parse_file(_fixture_path("csharp", "sample.cs"))
        class_names = [n.name for n in result.nodes if n.node_type == "class"]
        assert "Service" in class_names
        assert "IWorker" in class_names
        assert "Point" in class_names
        assert "Person" in class_names
        assert "Color" in class_names

    def test_parses_methods_and_constructors(self):
        result = ast_parser.parse_file(_fixture_path("csharp", "sample.cs"))
        func_names = [n.name for n in result.nodes if n.node_type == "function"]
        assert "Service" in func_names
        assert "Run" in func_names
        assert "Go" in func_names
        assert "Helper" in func_names

    def test_extracts_direct_and_member_calls(self):
        result = ast_parser.parse_file(_fixture_path("csharp", "sample.cs"))
        calls = {e["to"] for e in result.edges if e["type"] == "CALLS"}
        assert {"Helper", "Go", "Run", "WriteLine"} <= calls

    def test_parses_file_scoped_namespace(self):
        result = ast_parser.parse_file(_fixture_path("csharp", "filescope.cs"))
        assert result.error is None
        class_names = [n.name for n in result.nodes if n.node_type == "class"]
        assert "Demo.FileScoped" in class_names
        assert "Entry" in class_names

    def test_malformed_source_does_not_crash(self):
        result = ast_parser.parse_file(_fixture_path("csharp", "malformed.cs"))
        assert result.error is None
        assert result.file_hash


class TestExistingLanguagesUnchanged:
    def test_previous_fixtures_still_parse(self):
        expectations = {
            ("go", "main.go"): ("NewServer", "Server"),
            ("rust", "main.rs"): ("start_server", "Config"),
            ("java", "Server.java"): ("start", "Server"),
            ("c", "server.c"): ("start_server", "Config"),
            ("cpp", "server.cpp"): ("handleRequest", "Server"),
        }
        for (lang, filename), (function_name, class_name) in expectations.items():
            result = ast_parser.parse_file(_fixture_path(lang, filename))
            assert result.error is None
            functions = {n.name for n in result.nodes if n.node_type == "function"}
            classes = {n.name for n in result.nodes if n.node_type == "class"}
            assert function_name in functions
            assert class_name in classes

    def test_python_typescript_and_javascript_symbols(self, tmp_path):
        samples = {
            "app.py": (
                "def helper():\n    return 1\nclass Box:\n    pass\n",
                "helper",
                "Box",
            ),
            "app.ts": (
                "function helper() { return 1; }\nclass Box {}\n",
                "helper",
                "Box",
            ),
            "app.js": (
                "function helper() { return 1; }\nclass Box {}\n",
                "helper",
                "Box",
            ),
        }
        for filename, (source, function_name, class_name) in samples.items():
            path = tmp_path / filename
            path.write_text(source, encoding="utf-8")
            result = ast_parser.parse_file(str(path))
            assert result.error is None
            functions = {n.name for n in result.nodes if n.node_type == "function"}
            classes = {n.name for n in result.nodes if n.node_type == "class"}
            assert function_name in functions
            assert class_name in classes


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
