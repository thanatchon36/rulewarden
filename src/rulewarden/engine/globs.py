"""Deterministic path globbing: `**/` spans directories, `*` stays within one segment."""

from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=4096)
def glob_to_regex(pattern: str) -> re.Pattern[str]:
    pat = pattern.strip()
    while pat.startswith("./"):
        pat = pat[2:]
    pat = pat.lstrip("/")
    anchored = "/" in pat.rstrip("/")
    if pat.endswith("/"):
        pat += "**"
    out: list[str] = []
    i = 0
    n = len(pat)
    while i < n:
        c = pat[i]
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pat.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            j = pat.find("]", i + 1)
            if j == -1:
                out.append(re.escape(c))
                i += 1
            else:
                body = pat[i + 1 : j]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\") + "]")
                i = j + 1
        else:
            out.append(re.escape(c))
            i += 1
    core = "".join(out)
    if not anchored:
        core = "(?:.*/)?" + core
    return re.compile(r"\A" + core + r"\Z", re.DOTALL)


def match_path(path: str, pattern: str) -> bool:
    return glob_to_regex(pattern).match(path) is not None


def match_any(path: str, patterns: tuple[str, ...] | list[str]) -> bool:
    return any(match_path(path, p) for p in patterns)


def selected(path: str, include: tuple[str, ...], exclude: tuple[str, ...]) -> bool:
    """Synthetic targets such as `:commit-msg` are selected only when named explicitly."""
    if path.startswith(":"):
        return path in include and path not in exclude
    return match_any(path, include) and not match_any(path, exclude)
