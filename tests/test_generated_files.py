"""Committed generated files must match their generators (run `make paper docs` to refresh)."""

from __future__ import annotations

import html
import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _script(relpath: str) -> ModuleType:
    path = ROOT / relpath
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_paper_markdown_is_rendered_from_main() -> None:
    render = _script("paper/render.py")
    text, missing = render.render((ROOT / "paper" / "main.md").read_text(encoding="utf-8"))
    assert missing == []
    assert render.unverified_citations(text) == []
    assert (ROOT / "paper" / "paper.md").read_text(encoding="utf-8") == text, (
        "paper/paper.md is stale: run make paper"
    )


def test_reference_pages_match_the_code() -> None:
    gen = _script("docs/gen_reference.py")
    pages = ROOT / "docs" / "pages"
    assert (pages / "cli.md").read_text(encoding="utf-8") == gen.cli_page() + "\n", (
        "docs/pages/cli.md is stale: run make docs"
    )
    assert (pages / "rules.md").read_text(encoding="utf-8") == gen.rules_page() + "\n", (
        "docs/pages/rules.md is stale: run make docs"
    )


def test_readme_findings_block_matches_results() -> None:
    findings = _script("paper/findings.py")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert findings.START in readme and findings.END in readme
    assert findings.update_readme(readme) == readme, "README findings are stale: run make paper"


def test_web_reader_and_pdf_are_present() -> None:
    reader = (ROOT / "docs" / "pages" / "paper" / "index.html").read_text(encoding="utf-8")
    for marker in ("<!--META-->", "<!--RESULTS-->", "<!--COLOPHON-->"):
        assert marker not in reader
    for _, _, statement, _ in _script("paper/findings.py").rows():
        assert html.escape(statement) in reader
    for pdf in (ROOT / "paper" / "paper.pdf", ROOT / "docs" / "pages" / "paper" / "paper.pdf"):
        assert pdf.read_bytes()[:5] == b"%PDF-"
