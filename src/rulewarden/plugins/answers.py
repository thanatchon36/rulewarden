"""Heuristic: code that special-cases literal test inputs instead of computing results (advisory)."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any

from rulewarden.engine.checks import Hit, Target


def _is_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.Tuple | ast.List):
        return all(_is_literal(e) for e in node.elts)
    return isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant)


def literal_lookup(target: Target, options: Mapping[str, Any]) -> list[Hit]:
    """Flag `if <param> == <literal>: return <literal>` chains and literal-keyed answer dicts.

    min_branches (default 2) literal-compare-and-return branches in one function trigger a hit.
    """
    min_branches = int(options.get("min_branches", 2))
    if target.content is None or not target.path.endswith(".py"):
        return []
    try:
        tree = ast.parse(target.content)
    except (SyntaxError, ValueError):
        return []
    added = {n for n, _ in target.added}
    hits: list[Hit] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        params = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
        branches: list[int] = []
        for node in ast.walk(fn):
            if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
                continue
            test = node.test
            left_is_param = isinstance(test.left, ast.Name) and test.left.id in params
            if not (
                left_is_param and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq | ast.In)
            ):
                continue
            if not _is_literal(test.comparators[0]):
                continue
            ret = node.body[0] if node.body else None
            if isinstance(ret, ast.Return) and ret.value is not None and _is_literal(ret.value):
                branches.append(node.lineno)
        if len(branches) >= min_branches and any(b in added for b in branches):
            hits.append(
                Hit(
                    branches[0],
                    f"{fn.name}() returns hard-coded results for {len(branches)} literal inputs",
                )
            )
    return hits
