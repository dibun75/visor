import tree_sitter
import tree_sitter_python

try:
    PY_LANGUAGE = tree_sitter.Language(tree_sitter_python.language(), "python")
    parser = tree_sitter.Parser()
    parser.language = PY_LANGUAGE
    tree = parser.parse(b"def foo():\n  pass\n")
    print(tree.root_node.sexp())
except Exception as e:
    try:
        PY_LANGUAGE = tree_sitter.Language(tree_sitter_python.language())
        parser = tree_sitter.Parser(PY_LANGUAGE)
        tree = parser.parse(b"def foo():\n  pass\n")
        print(tree.root_node.sexp())
    except Exception as e2:
        print(f"FAILED V1: {e}\nFAILED V2: {e2}")
