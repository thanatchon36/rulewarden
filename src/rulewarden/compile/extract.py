"""Extract rule-like lines from markdown instruction files (shared by `compile` and the corpus study)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_CUE_RE = re.compile(
    r"(?i)(^|[\s(\"'*_`-])(always|never|do not|don['’]?t|dont|must|should|shouldn['’]?t|prefer|avoid|use|"
    r"only|ensure|make sure|no|keep|run|write|add|include|follow|remember|important|required|forbidden|"
    r"instead of|rather than|do)\b"
)
_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_MD_RE = re.compile(r"\*\*|__|~~|^#+\s*|^>\s*")


@dataclass(frozen=True)
class RuleLine:
    lineno: int
    text: str


def strip_markdown(line: str) -> str:
    s = _BULLET_RE.sub("", line)
    s = _MD_RE.sub("", s.strip())
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return s.strip()


def is_rule_like(text: str) -> bool:
    if len(text) < 6 or len(text) > 400:
        return False
    if not re.search(r"[A-Za-z]{3}", text):
        return False
    return bool(_CUE_RE.search(text))


def extract(text: str) -> list[RuleLine]:
    """Rule-like lines outside fenced code blocks, headings, tables and HTML comments."""
    out: list[RuleLine] = []
    in_fence = False
    in_comment = False
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if "<!--" in stripped:
            in_comment = "-->" not in stripped.split("<!--", 1)[1]
            continue
        if in_comment:
            in_comment = "-->" not in stripped
            continue
        if not stripped or stripped.startswith(("#", "|", "---", "===")):
            continue
        body = strip_markdown(line)
        if is_rule_like(body):
            out.append(RuleLine(i, body))
    return out
