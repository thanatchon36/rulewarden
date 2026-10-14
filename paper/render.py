"""Render paper/main.md to paper/build/main.md, filling every number from generated results.

Placeholders: {{corpus:dotted.path|filter}}, {{bench:dotted.path|filter}}, {{table:name}}.
Sources: corpus/data/summary.json, bench/results/summary.json, paper/tables/<name>.md.
Filters: pct (0.1234 -> 12.3%), ci (pair -> 12.3–45.6%), int, f2, f3, raw (default).
An unresolved placeholder fails the build: no number is typed by hand.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
SOURCES = {
    "corpus": ROOT / "corpus" / "data" / "summary.json",
    "bench": ROOT / "bench" / "results" / "summary.json",
}
_PH = re.compile(r"\{\{(corpus|bench|table):([A-Za-z0-9_.\-]+)(?:\|(\w+))?\}\}")


def _get(data: Any, dotted: str) -> Any:
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(dotted)
    return cur


def _fmt(value: Any, filt: str | None) -> str:
    if value is None:
        return "n/a"
    if filt == "pct":
        return f"{100 * float(value):.1f}%"
    if filt == "ci":
        lo, hi = value
        return f"{100 * float(lo):.1f}–{100 * float(hi):.1f}%"
    if filt == "int":
        return f"{round(float(value)):,}"
    if filt == "f2":
        return f"{float(value):.2f}"
    if filt == "f3":
        return f"{float(value):.3f}"
    if filt == "p":
        v = float(value)
        return "< 0.001" if v < 0.001 else f"{v:.3f}"
    return str(value)


def render(text: str) -> tuple[str, list[str]]:
    cache: dict[str, Any] = {}
    missing: list[str] = []

    def sub(m: re.Match[str]) -> str:
        src, path, filt = m.group(1), m.group(2), m.group(3)
        if src == "table":
            t = PAPER / "tables" / f"{path}.md"
            if not t.exists():
                missing.append(m.group(0))
                return m.group(0)
            return t.read_text(encoding="utf-8").rstrip("\n")
        if src not in cache:
            f = SOURCES[src]
            cache[src] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        try:
            return _fmt(_get(cache[src], path), filt)
        except (KeyError, IndexError, TypeError, ValueError):
            missing.append(m.group(0))
            return m.group(0)

    return _PH.sub(sub, text), missing


def main() -> int:
    out_dir = PAPER / "build"
    out_dir.mkdir(exist_ok=True)
    text, missing = render((PAPER / "main.md").read_text(encoding="utf-8"))
    if missing:
        for m in missing:
            print(f"unresolved: {m}", file=sys.stderr)
        return 1
    (out_dir / "main.md").write_text(text, encoding="utf-8")
    print(f"rendered {out_dir / 'main.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
