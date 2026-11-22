"""Check that relative Markdown links in the public docs point at real files.

External URLs and in-page anchors are skipped, so this runs offline.
"""

import re
from pathlib import Path
from urllib.parse import unquote

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# [text](target) and ![alt](target), with an optional "title".
_INLINE_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
# [label]: target
_REFERENCE_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+.*)?$", re.M)
# <img src="..."> and <a href="..."> in raw HTML blocks.
_HTML_ATTR = re.compile(r"<(?:img|a|source)\b[^>]*?\b(?:src|href)=\"([^\"]+)\"", re.I)
_FENCE = re.compile(r"^(```|~~~).*?^\1", re.M | re.S)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "data:", "#")


def _public_docs():
    files = [REPO_ROOT / "README.md", REPO_ROOT / "CONTRIBUTING.md"]
    files += sorted((REPO_ROOT / "docs").rglob("*.md"))
    return [f for f in files if f.is_file()]


def relative_links(text: str):
    """Yield link targets in *text* that refer to local files."""
    text = _FENCE.sub("", text)
    text = _INLINE_CODE.sub("", text)
    for pattern in (_INLINE_LINK, _REFERENCE_DEF, _HTML_ATTR):
        for match in pattern.finditer(text):
            target = match.group(1).strip()
            if not target or target.lower().startswith(_SKIP_PREFIXES):
                continue
            if "://" in target:
                continue
            path = target.split("#", 1)[0].split("?", 1)[0]
            if path:
                yield target, unquote(path)


def broken_links(doc: Path):
    broken = []
    for target, path in relative_links(doc.read_text(encoding="utf-8")):
        base = REPO_ROOT if path.startswith("/") else doc.parent
        if not (base / path.lstrip("/")).exists():
            broken.append(target)
    return broken


@pytest.mark.parametrize(
    "doc", _public_docs(), ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_relative_links_resolve(doc):
    assert broken_links(doc) == []


def test_checker_flags_missing_targets(tmp_path):
    doc = tmp_path / "doc.md"
    (tmp_path / "exists.md").write_text("ok", encoding="utf-8")
    doc.write_text(
        "[ok](exists.md) [anchor](exists.md#part) [gone](missing.md)\n"
        "![img](img/none.png) [web](https://example.com) [here](#top)\n"
        "[ref]: also-missing.md\n"
        "```\n[in code](not-checked.md)\n```\n",
        encoding="utf-8",
    )
    targets = [path for _, path in relative_links(doc.read_text(encoding="utf-8"))]
    assert "not-checked.md" not in targets
    assert "https://example.com" not in targets
    missing = [
        t for t, p in relative_links(doc.read_text()) if not (tmp_path / p).exists()
    ]
    assert sorted(missing) == ["also-missing.md", "img/none.png", "missing.md"]
