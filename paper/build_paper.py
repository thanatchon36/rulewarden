"""Typeset paper/paper.md into paper/paper.pdf and the web reader docs/pages/paper/index.html.

One source, two outputs, so they cannot disagree. pandoc converts paper.md (rendered from main.md
by render.py) to Typst with paper/rulewarden.typ, compiled by the typst wheel, and to an HTML
page with paper/reader.html (figures copied next to it, so every line stays scannable). The
reader's masthead and results strip (paper/findings.py) come from the generated summaries.
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

from findings import SOURCES, TAGS, Row, load, rows

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
MARKDOWN = PAPER / "paper.md"
TYPST_SOURCE = PAPER / "build" / "paper.typ"
PDF = PAPER / "paper.pdf"
READER_DIR = ROOT / "docs" / "pages" / "paper"
BIB = PAPER / "refs.verified.bib"
REPO_URL = "https://github.com/thanatchon36/rulewarden"


def _pandoc() -> str:
    found = shutil.which("pandoc")
    if found is None:
        raise FileNotFoundError("pandoc not found; install pandoc 3.x (brew install pandoc)")
    return found


def _common_args() -> list[str]:
    return [
        "--from=markdown+smart",
        "--citeproc",
        f"--bibliography={BIB.name}",
        "--csl=ieee.csl",
        "--number-sections",
        "--wrap=none",
        "--metadata=link-citations:true",
        "--metadata=reference-section-title:References",
    ]


def build_pdf() -> Path:
    TYPST_SOURCE.parent.mkdir(exist_ok=True)
    subprocess.run(
        [
            _pandoc(),
            MARKDOWN.name,
            "--to=typst",
            "--template=rulewarden.typ",
            "-o",
            str(TYPST_SOURCE),
            *_common_args(),
        ],
        cwd=PAPER,
        check=True,
    )
    source = TYPST_SOURCE.read_text(encoding="utf-8").replace(
        'image("figures/', 'image("../figures/'
    )
    TYPST_SOURCE.write_text(source, encoding="utf-8")
    import typst

    typst.compile(str(TYPST_SOURCE), output=str(PDF), root=str(ROOT))
    return PDF


def _items(results: list[Row]) -> str:
    return "\n".join(
        f'<li class="r r-{k}"><span class="r-id">{html.escape(i)}</span>'
        f'<span class="r-text">{html.escape(t)}<small>{html.escape(d)}</small></span>'
        f'<span class="r-tag">{TAGS[k]}</span></li>'
        for i, k, t, d in results
    )


def build_reader() -> Path:
    corpus = load(SOURCES["corpus"])
    bench = load(SOURCES["bench"])
    refs = load(PAPER / "refs_verified.json")["entries"]
    refs = list(refs.values()) if isinstance(refs, dict) else refs
    verified = sum(1 for r in refs if r.get("status") == "verified")
    version = re.search(
        r'^__version__ = "([^"]+)"', (ROOT / "src" / "rulewarden" / "__init__.py").read_text(), re.M
    )
    assert version is not None
    meta = (
        f"<b>rulewarden v{version.group(1)}</b> · {corpus['n_files']} instruction files · "
        f"{corpus['n_lines']:,} rule-like lines · {bench['n_runs']} agent runs (+{bench['n_pilot_runs_excluded']} pilot) · "
        f"{verified} verified references"
    )
    actions = (
        '<li><a href="paper.pdf">Download PDF</a></li>'
        f'<li><a href="{REPO_URL}">Source code</a></li>'
        '<li><a href="../">Documentation</a></li>'
        f'<li><a href="{REPO_URL}/blob/main/bench/ANALYSIS_PLAN.md">Pre-registered plan</a></li>'
    )
    note = (
        "Pre-registered hypotheses H1–H6 and the other research questions, generated from the results files. "
        "“null” means no detectable difference, here because every condition reached the ceiling."
    )
    colophon = (
        "<p>Manuscript, tool, corpus pipeline and benchmark written by Claude Opus 5.5 (Anthropic) under the author's "
        "specification; the author is responsible for the content.</p>"
        "<p>Rendered from <code>paper/main.md</code>. Every number comes from generated results "
        "(<code>corpus/data/summary.json</code>, <code>bench/results/summary.json</code>, "
        "<code>bench/results/rq3.json</code>, <code>paper/data/dogfood_audit.json</code>). "
        "<code>make replay</code> recomputes the benchmark without an API key.</p>"
    )
    READER_DIR.mkdir(parents=True, exist_ok=True)
    out = READER_DIR / "index.html"
    subprocess.run(
        [
            _pandoc(),
            MARKDOWN.name,
            "--to=html5",
            "--template=reader.html",
            "--standalone",
            "--toc",
            "--toc-depth=2",
            "--resource-path=.",
            "--metadata=pagetitle:rulewarden — paper",
            "-o",
            str(out),
            *_common_args(),
        ],
        cwd=PAPER,
        check=True,
    )
    page = out.read_text(encoding="utf-8")
    for marker, value in (
        ("<!--META-->", meta),
        ("<!--ACTIONS-->", actions),
        ("<!--RESULTS-NOTE-->", note),
        ("<!--RESULTS-->", _items(rows())),
        ("<!--COLOPHON-->", colophon),
    ):
        assert marker in page, marker
        page = page.replace(marker, value)
    out.write_text(page, encoding="utf-8")
    shutil.copy(PDF, READER_DIR / "paper.pdf")
    figures = READER_DIR / "figures"
    figures.mkdir(exist_ok=True)
    for png in sorted(re.findall(r'src="figures/([\w.-]+\.png)"', page)):
        shutil.copy(PAPER / "figures" / png, figures / png)
    return out


def main() -> int:
    pdf = build_pdf()
    reader = build_reader()
    sys.stdout.write(f"built {pdf.relative_to(ROOT)} and {reader.relative_to(ROOT)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
