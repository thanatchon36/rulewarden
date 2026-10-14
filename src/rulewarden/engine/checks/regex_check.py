"""Bounded regex engine: forbid or require a pattern on added lines, hunks, files, paths or commands."""

from __future__ import annotations

import io
import re
import tokenize
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from rulewarden.engine.checks import EngineContext, Hit, Target, require_keys
from rulewarden.engine.checks.comments import comment_text
from rulewarden.engine.globs import match_any
from rulewarden.engine.regexsafe import compile_safe
from rulewarden.engine.schema import On
from rulewarden.errors import SchemaError

_KEYS = {"pattern", "patterns", "flags", "mode", "unless", "unless_changed", "within", "detail"}


@dataclass(frozen=True)
class Prepared:
    patterns: tuple[re.Pattern[str], ...]
    unless: re.Pattern[str] | None
    mode: str
    within: str
    detail: str
    unless_changed: tuple[str, ...] = ()


def prepare(params: Mapping[str, Any], on: On, ctx: EngineContext) -> Prepared:
    require_keys(params, _KEYS, set(), "regex")
    raw = params.get("patterns") or ([params["pattern"]] if "pattern" in params else [])
    if (
        isinstance(raw, str)
        or not isinstance(raw, list)
        or not raw
        or not all(isinstance(p, str) for p in raw)
    ):
        raise SchemaError("regex: 'pattern' (string) or 'patterns' (non-empty list) is required")
    flags = params.get("flags", [])
    if isinstance(flags, str):
        flags = list(flags)
    mode = params.get("mode", "forbid")
    if mode not in ("forbid", "require"):
        raise SchemaError("regex: mode must be 'forbid' or 'require'")
    if mode == "require" and on not in (On.FILE, On.COMMAND):
        raise SchemaError("regex: mode 'require' needs on: file or on: command")
    within = params.get("within", "all")
    if within not in ("all", "comments", "code"):
        raise SchemaError("regex: within must be 'all', 'comments' or 'code'")
    unless = params.get("unless")
    if unless is not None and not isinstance(unless, str):
        raise SchemaError("regex: unless must be a string pattern")
    detail = params.get("detail", "")
    if not isinstance(detail, str):
        raise SchemaError("regex: detail must be a string")
    return Prepared(
        patterns=tuple(compile_safe(p, flags) for p in raw),
        unless=compile_safe(unless, flags) if unless else None,
        mode=mode,
        within=within,
        detail=detail,
        unless_changed=_globs(params.get("unless_changed", [])),
    )


def _globs(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise SchemaError("unless_changed must be a list of globs")
    return tuple(value)


def _docstring_lines(content: str) -> frozenset[int]:
    lines: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(content).readline):
            if tok.type == tokenize.STRING and tok.string.lstrip("rbuRBU").startswith(
                ('"""', "'''")
            ):
                lines.update(range(tok.start[0], tok.end[0] + 1))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return frozenset()
    return frozenset(lines)


def _scoped(
    prep: Prepared, path: str, lineno: int, text: str, doc_lines: frozenset[int]
) -> str | None:
    if prep.within == "all":
        return text
    comment = text if lineno in doc_lines else comment_text(path, text)
    if prep.within == "comments":
        return comment
    if comment is None:
        return text
    return text[: len(text) - len(comment)] if text.endswith(comment) else None


def _search(prep: Prepared, text: str) -> re.Match[str] | None:
    if prep.unless is not None and prep.unless.search(text):
        return None
    for p in prep.patterns:
        m = p.search(text)
        if m:
            return m
    return None


def _line_too_long(text: str, ctx: EngineContext) -> bool:
    return len(text) > ctx.limits.max_line_chars


def run(prep: Prepared, on: On, target: Target, ctx: EngineContext) -> list[Hit]:
    if prep.unless_changed and any(match_any(p, prep.unless_changed) for p in target.changeset):
        return []
    hits: list[Hit] = []
    if on is On.COMMAND:
        cmd = target.command or ""
        found = _search(prep, cmd) is not None
        if found == (prep.mode == "forbid"):
            hits.append(Hit(None, prep.detail))
        return hits
    if on is On.PATH:
        if _search(prep, target.path):
            hits.append(Hit(None, prep.detail))
        return hits
    doc_lines: frozenset[int] = frozenset()
    if prep.within != "all" and target.content is not None and target.path.endswith(".py"):
        doc_lines = _docstring_lines(target.content)
    if on is On.ADDED_LINES:
        for lineno, text in target.added:
            if _line_too_long(text, ctx):
                hits.append(
                    Hit(lineno, f"line longer than {ctx.limits.max_line_chars} chars", True)
                )
                continue
            scoped = _scoped(prep, target.path, lineno, text, doc_lines)
            if scoped is not None and _search(prep, scoped):
                hits.append(Hit(lineno, prep.detail))
        return hits
    if on is On.HUNKS:
        for block in target.blocks:
            if any(_line_too_long(t, ctx) for t in block.lines):
                hits.append(
                    Hit(block.start, f"line longer than {ctx.limits.max_line_chars} chars", True)
                )
                continue
            scoped_lines = [
                _scoped(prep, target.path, block.start + k, t, doc_lines) or ""
                for k, t in enumerate(block.lines)
            ]
            text = "\n".join(scoped_lines)
            m = _search(prep, text)
            if m:
                hits.append(Hit(block.start + text[: m.start()].count("\n"), prep.detail))
        return hits
    # On.FILE
    content = target.content
    if content is None:
        return hits
    if len(content.encode("utf-8")) > ctx.limits.max_file_bytes:
        return [Hit(None, f"file larger than {ctx.limits.max_file_bytes} bytes", True)]
    lines = content.split("\n")
    if any(_line_too_long(t, ctx) for t in lines):
        return [Hit(None, f"line longer than {ctx.limits.max_line_chars} chars", True)]
    if prep.within != "all":
        content = "\n".join(
            _scoped(prep, target.path, i + 1, t, doc_lines) or "" for i, t in enumerate(lines)
        )
    if prep.mode == "require":
        if _search(prep, content) is None:
            hits.append(Hit(None, prep.detail))
        return hits
    seen: set[int] = set()
    for p in prep.patterns:
        for m in p.finditer(content):
            line = content[: m.start()].count("\n") + 1
            matched_line = lines[line - 1] if line - 1 < len(lines) else ""
            if prep.unless is not None and prep.unless.search(matched_line):
                continue
            if line not in seen:
                seen.add(line)
                hits.append(Hit(line, prep.detail))
    return sorted(hits, key=lambda h: h.line or 0)
