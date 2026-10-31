import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.paths import is_within

with tempfile.TemporaryDirectory() as directory:
    parent = Path(directory)
    root = parent / "project"
    root.mkdir()
    child = root / "src" / "module.py"
    child.parent.mkdir()
    child.touch()
    sibling = parent / "project-secrets" / "token.txt"
    sibling.parent.mkdir()
    sibling.touch()

    assert is_within(root, child)
    assert is_within(root, root)
    assert not is_within(root, sibling)
    assert not is_within(root, parent)
print("path checks passed")
