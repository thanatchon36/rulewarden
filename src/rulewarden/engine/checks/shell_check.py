"""Opt-in shell engine: run an allowlisted binary with no shell, a scrubbed env and a timeout.

Content goes to stdin; a non-zero exit is a hit whose detail is the first stdout line.
Network isolation is not enforced by the OS here; see docs/security.md.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from rulewarden.engine.checks import EngineContext, Hit, Target, require_keys
from rulewarden.engine.schema import On
from rulewarden.errors import EngineError, SchemaError

_KEYS = {"argv", "detail"}
_SAFE_PATH = "/usr/bin:/bin"


@dataclass(frozen=True)
class Prepared:
    argv: tuple[str, ...]
    detail: str


def prepare(params: Mapping[str, Any], on: On, ctx: EngineContext) -> Prepared:
    require_keys(params, _KEYS, {"argv"}, "shell")
    argv = params["argv"]
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise SchemaError("shell: argv must be a non-empty list of strings (no shell is used)")
    return Prepared(argv=tuple(argv), detail=str(params.get("detail", "")))


def run(prep: Prepared, on: On, target: Target, ctx: EngineContext) -> list[Hit]:
    if not ctx.allow_shell:
        raise EngineError(
            "shell engine is disabled; a human must enable engines.shell in .rulewarden/config.yaml"
        )
    name = prep.argv[0]
    if name not in ctx.shell_allowlist:
        raise EngineError(f"shell engine: {name!r} is not in engines.shell.allowlist")
    exe = shutil.which(name, path=_SAFE_PATH)
    if exe is None:
        raise EngineError(f"shell engine: {name!r} not found on {_SAFE_PATH}")
    data = target.command if on is On.COMMAND else target.content
    if data is None:
        return []
    with tempfile.TemporaryDirectory(prefix="rulewarden-") as tmp:
        env = {
            "PATH": _SAFE_PATH,
            "HOME": tmp,
            "TMPDIR": tmp,
            "LC_ALL": "C",
            "RULEWARDEN_PATH": target.path,
        }
        try:
            proc = subprocess.run(
                [exe, *prep.argv[1:]],
                input=data,
                capture_output=True,
                text=True,
                cwd=tmp,
                env=env,
                timeout=ctx.limits.per_check_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise EngineError(
                f"shell engine: {name} timed out after {ctx.limits.per_check_s:g}s"
            ) from exc
    if proc.returncode == 0:
        return []
    first = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else prep.detail
    return [Hit(None, first[:200])]
