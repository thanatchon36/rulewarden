"""Python AST checks. A file that does not parse yields an 'unverifiable' hit (fail-closed)."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from rulewarden.engine.checks import EngineContext, Hit, Target, require_keys
from rulewarden.engine.schema import On
from rulewarden.errors import SchemaError

_KEYS = {"rule", "names", "max", "detail"}
_RULES = (
    "bare-except",
    "call",
    "import",
    "docstring-max-lines",
    "function-max-lines",
    "broad-except-pass",
)


@dataclass(frozen=True)
class Prepared:
    rule: str
    names: frozenset[str]
    max: int
    detail: str


def prepare(params: Mapping[str, Any], on: On, ctx: EngineContext) -> Prepared:
    require_keys(params, _KEYS, {"rule"}, "ast")
    rule = params["rule"]
    if rule not in _RULES:
        raise SchemaError(f"ast: rule must be one of {list(_RULES)}")
    names = params.get("names", [])
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise SchemaError("ast: names must be a list of strings")
    if rule in ("call", "import") and not names:
        raise SchemaError(f"ast: rule {rule!r} needs 'names'")
    mx = params.get("max", 0)
    if rule.endswith("max-lines") and (not isinstance(mx, int) or isinstance(mx, bool) or mx < 1):
        raise SchemaError(f"ast: rule {rule!r} needs a positive integer 'max'")
    return Prepared(
        rule=rule, names=frozenset(names), max=int(mx), detail=str(params.get("detail", ""))
    )


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _docstring_node(node: ast.AST) -> ast.Constant | None:
    body = getattr(node, "body", None)
    if not body or not isinstance(body[0], ast.Expr):
        return None
    val = body[0].value
    if isinstance(val, ast.Constant) and isinstance(val.value, str):
        return val
    return None


def run(prep: Prepared, on: On, target: Target, ctx: EngineContext) -> list[Hit]:
    if target.content is None:
        return []
    if len(target.content.encode("utf-8")) > ctx.limits.max_file_bytes:
        return [Hit(None, f"file larger than {ctx.limits.max_file_bytes} bytes", True)]
    try:
        tree = ast.parse(target.content, filename=target.path)
    except (SyntaxError, ValueError) as exc:
        line = getattr(exc, "lineno", None)
        return [Hit(line, f"cannot parse Python: {getattr(exc, 'msg', exc)}", True)]
    hits: list[Hit] = []
    for node in ast.walk(tree):
        if prep.rule == "bare-except" and isinstance(node, ast.ExceptHandler) and node.type is None:
            hits.append(Hit(node.lineno, prep.detail or "bare except"))
        elif prep.rule == "broad-except-pass" and isinstance(node, ast.ExceptHandler):
            broad = node.type is None or _call_name(node.type) in ("Exception", "BaseException")
            if broad and all(isinstance(s, ast.Pass) for s in node.body):
                hits.append(Hit(node.lineno, prep.detail or "exception swallowed"))
        elif prep.rule == "call" and isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in prep.names:
                hits.append(Hit(node.lineno, prep.detail or f"call to {name}()"))
        elif prep.rule == "import" and isinstance(node, ast.Import | ast.ImportFrom):
            mods = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for mod in mods:
                if mod in prep.names or mod.split(".")[0] in prep.names:
                    hits.append(Hit(node.lineno, prep.detail or f"import of {mod}"))
        elif prep.rule == "docstring-max-lines" and isinstance(
            node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ):
            doc = _docstring_node(node)
            if doc is not None:
                n = len(str(doc.value).strip("\n").split("\n"))
                if n > prep.max:
                    hits.append(
                        Hit(doc.lineno, prep.detail or f"docstring has {n} lines (max {prep.max})")
                    )
        elif prep.rule == "function-max-lines" and isinstance(
            node, ast.FunctionDef | ast.AsyncFunctionDef
        ):
            end = node.end_lineno or node.lineno
            n = end - node.lineno + 1
            if n > prep.max:
                hits.append(
                    Hit(
                        node.lineno,
                        prep.detail or f"function {node.name} has {n} lines (max {prep.max})",
                    )
                )
    return sorted(set(hits), key=lambda h: (h.line or 0, h.detail))
