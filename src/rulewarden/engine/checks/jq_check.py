"""jq engine: a jq filter over a JSON file; each `true` or string output is a hit."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from rulewarden.engine.checks import EngineContext, Hit, Target, require_keys
from rulewarden.engine.schema import On
from rulewarden.errors import EngineError, SchemaError

_KEYS = {"filter", "detail"}


@dataclass(frozen=True)
class Prepared:
    filter: str
    detail: str


def prepare(params: Mapping[str, Any], on: On, ctx: EngineContext) -> Prepared:
    require_keys(params, _KEYS, {"filter"}, "jq")
    flt = params["filter"]
    if not isinstance(flt, str) or not flt.strip():
        raise SchemaError("jq: filter must be a non-empty string")
    return Prepared(filter=flt, detail=str(params.get("detail", "")))


def run(prep: Prepared, on: On, target: Target, ctx: EngineContext) -> list[Hit]:
    if target.content is None:
        return []
    jq = shutil.which("jq")
    if jq is None:
        raise EngineError("jq engine: 'jq' is not on PATH")
    try:
        proc = subprocess.run(
            [jq, "-c", prep.filter],
            input=target.content,
            capture_output=True,
            text=True,
            timeout=ctx.limits.per_check_s,
            env={"LC_ALL": "C", "PATH": "/usr/bin:/bin"},
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise EngineError(f"jq engine: timed out after {ctx.limits.per_check_s:g}s") from exc
    if proc.returncode != 0:
        if "parse error" in proc.stderr.lower() or "cannot" in proc.stderr.lower():
            return [Hit(None, f"invalid JSON: {proc.stderr.strip()[:120]}", True)]
        raise EngineError(f"jq engine: exit {proc.returncode}: {proc.stderr.strip()[:200]}")
    hits: list[Hit] = []
    for raw in proc.stdout.splitlines():
        if not raw.strip():
            continue
        val = json.loads(raw)
        if val is True:
            hits.append(Hit(None, prep.detail))
        elif isinstance(val, str):
            hits.append(Hit(None, val))
    return hits
