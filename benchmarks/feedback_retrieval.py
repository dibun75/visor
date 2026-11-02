"""Deterministic retrieval-only check for explicit feedback.

This does not call a coding agent and does not measure whether a patch is correct.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def run_feedback_benchmark() -> dict:
    home = tempfile.mkdtemp(prefix="visor-feedback-bench-")
    project = Path(tempfile.mkdtemp(prefix="visor-feedback-project-"))
    previous = {
        "VISOR_HOME": os.environ.get("VISOR_HOME"),
        "WORKSPACE_ROOT": os.environ.get("WORKSPACE_ROOT"),
        "VISOR_RETRIEVAL_MODE": os.environ.get("VISOR_RETRIEVAL_MODE"),
    }
    os.environ["VISOR_HOME"] = home
    os.environ["WORKSPACE_ROOT"] = str(project)
    os.environ["VISOR_RETRIEVAL_MODE"] = "lexical"
    try:
        (project / "pyproject.toml").write_text(
            "[project]\nname='bench'\n", encoding="utf-8"
        )
        files = {
            "anchor.py": 'def shared():\n    """anchor shared"""\n    return 1\n',
            "left.py": 'def shared():\n    """left"""\n    return 1\n',
            "right.py": 'def shared():\n    """right"""\n    return 1\n',
            "other.py": 'def database():\n    """migration plan"""\n    return 1\n',
        }
        for relative, source in files.items():
            (project / relative).write_text(source, encoding="utf-8")

        from visor.db.client import VectorDBClient
        from visor.feedback import record_feedback
        from visor.parser.watcher import index_workspace
        from visor.tools.context_engine import build_context

        VectorDBClient._instance = None
        client = VectorDBClient()
        client.reinitialize(str(project))
        index_workspace(str(project))

        def order(query: str) -> list[str]:
            return [
                Path(item["file_path"]).name for item in build_context(query)["context"]
            ]

        baseline = order("shared anchor")
        unrelated_before = order("database migration plan")
        record_feedback(
            query="shared anchor",
            file_path="right.py",
            verdict="useful",
            intent="DEFAULT",
        )
        exact = order("shared anchor")
        similar = order("shared anchor export")
        unrelated_after = order("database migration plan")
        passed = (
            baseline.index("right.py") > baseline.index("left.py")
            and exact.index("right.py") < exact.index("left.py")
            and similar.index("right.py") < similar.index("left.py")
            and unrelated_before == unrelated_after
        )
        return {
            "passed": passed,
            "baseline": baseline,
            "exact_query": exact,
            "similar_query": similar,
            "unrelated_before": unrelated_before,
            "unrelated_after": unrelated_after,
            "claim": "retrieval order only; not an agent-correctness result",
        }
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(home, ignore_errors=True)
        shutil.rmtree(project, ignore_errors=True)


def main() -> int:
    result = run_feedback_benchmark()
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
