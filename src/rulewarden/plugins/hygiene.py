"""Heuristic hygiene plugins (advisory only): restating comments and comment density."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from rulewarden.engine.checks import Hit, Target
from rulewarden.engine.checks.comments import comment_text

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "to",
        "of",
        "and",
        "or",
        "for",
        "in",
        "on",
        "by",
        "with",
        "is",
        "it",
        "this",
        "that",
    }
)
_STEMS = (("ing", ""), ("ed", ""), ("es", ""), ("s", ""))


def _stem(w: str) -> str:
    for suf, rep in _STEMS:
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)] + rep
    return w


def tokens(text: str) -> set[str]:
    out: set[str] = set()
    for raw in _WORD.findall(text):
        for part in _CAMEL.sub(" ", raw).replace("_", " ").split():
            w = part.lower()
            if w not in _STOP and len(w) > 1:
                out.add(_stem(w))
    return out


_OP_WORDS = (
    ("+=", {"increment", "add"}),
    ("-=", {"decrement", "subtract"}),
    ("*=", {"multiply"}),
    ("/=", {"divide"}),
    ("==", {"check", "compare"}),
    ("=", {"set", "assign"}),
    ("(", {"call"}),
)


def code_tokens(code: str) -> set[str]:
    out = tokens(code)
    rest = code
    for op, words in _OP_WORDS:
        if op in rest:
            out |= words
            rest = rest.replace(op, " ")
    return out


def _overlap(comment: str, code: str) -> float:
    c = tokens(comment)
    if not c:
        return 0.0
    return len(c & code_tokens(code)) / len(c)


def restating_comment(target: Target, options: Mapping[str, Any]) -> list[Hit]:
    """Comment line whose tokens largely repeat the next code line (Appendix B, R-031)."""
    threshold = float(options.get("threshold", 0.8))
    if target.content is None:
        return []
    lines = target.content.split("\n")
    added = {n for n, _ in target.added}
    hits: list[Hit] = []
    for idx, line in enumerate(lines):
        lineno = idx + 1
        if lineno not in added:
            continue
        stripped = line.strip()
        comment = comment_text(target.path, line)
        if comment is None or not stripped or not stripped.startswith(("#", "//")):
            continue
        nxt = next((ln for ln in lines[idx + 1 :] if ln.strip()), "")
        if not nxt or (
            comment_text(target.path, nxt) is not None and nxt.strip().startswith(("#", "//"))
        ):
            continue
        score = _overlap(comment, nxt)
        if score >= threshold:
            hits.append(Hit(lineno, f"comment repeats the code below (overlap {score:.2f})"))
    return hits


def comment_density(target: Target, options: Mapping[str, Any]) -> list[Hit]:
    """Share of added non-blank lines that are full-line comments exceeds max_ratio."""
    max_ratio = float(options.get("max_ratio", 0.35))
    min_lines = int(options.get("min_lines", 8))
    code = 0
    comments = 0
    first: int | None = None
    for lineno, text in target.added:
        s = text.strip()
        if not s:
            continue
        if s.startswith(("#", "//")) and not s.startswith("#!"):
            comments += 1
            first = first or lineno
        else:
            code += 1
    total = code + comments
    if total >= min_lines and comments / total > max_ratio:
        return [
            Hit(first, f"{comments}/{total} added lines are comments (max ratio {max_ratio:.2f})")
        ]
    return []
