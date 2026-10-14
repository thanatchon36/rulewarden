"""Plain git hooks: pre-commit (staged diff), commit-msg (message prose), pre-push (pushed range)."""

from __future__ import annotations

import contextlib
import os
import shlex
import stat
import time
from pathlib import Path

from rulewarden.config import Config
from rulewarden.engine import audit, gitsrc
from rulewarden.engine.diff import Diff, synthesize_added
from rulewarden.engine.report import Result, render_text
from rulewarden.engine.runner import Request, _synthetic, run_check
from rulewarden.errors import RulewardenError

ZERO_SHA = "0" * 40
HOOKS = ("pre-commit", "commit-msg", "pre-push")


def _error(exc: Exception) -> Result:
    res = Result(fatal=True)
    res.findings.append(
        _synthetic(
            "RW-DIFF",
            "critical",
            "change could not be read",
            "fix the repository state; failing closed",
            detail=str(exc)[:300],
            kind="error",
        )
    )
    return res


def pre_commit(cfg: Config) -> Result:
    try:
        return run_check(cfg, Request(diff=gitsrc.staged_diff(cfg)))
    except RulewardenError as exc:
        return _error(exc)


def commit_msg(cfg: Config, msg_file: str) -> Result:
    text = Path(msg_file).read_text(encoding="utf-8", errors="replace")
    body = "\n".join(line for line in text.split("\n") if not line.startswith("#"))
    fc = synthesize_added(":commit-msg", body)
    return run_check(
        cfg, Request(diff=Diff(files=[fc], raw_sha256=""), check_protected_drift=False)
    )


def pre_push(cfg: Config, stdin_text: str) -> Result:
    """Check every pushed range; lines are '<local ref> <local sha> <remote ref> <remote sha>'."""
    merged = Result()
    for line in stdin_text.splitlines():
        parts = line.split()
        if len(parts) != 4 or parts[1] == ZERO_SHA:
            continue
        local_sha, remote_sha = parts[1], parts[3]
        base = remote_sha if remote_sha != ZERO_SHA else gitsrc.EMPTY_TREE
        try:
            if base == gitsrc.EMPTY_TREE:
                diff = gitsrc.tree_diff(cfg, base, local_sha)
            else:
                diff = gitsrc.range_diff(cfg, base, local_sha)
            res = run_check(cfg, Request(diff=diff, check_protected_drift=False))
        except RulewardenError as exc:
            res = _error(exc)
        merged.findings.extend(res.findings)
        merged.errors.extend(res.errors)
        merged.fatal = merged.fatal or res.fatal
        merged.ruleset_sha256 = res.ruleset_sha256
    return merged


def run(cfg: Config, hook: str, args: tuple[str, ...], stdin_text: str) -> tuple[Result, str]:
    t0 = time.monotonic()
    if hook == "pre-commit":
        res = pre_commit(cfg)
    elif hook == "commit-msg":
        res = (
            commit_msg(cfg, args[0])
            if args
            else _error(ValueError("commit-msg needs the message file"))
        )
    elif hook == "pre-push":
        res = pre_push(cfg, stdin_text)
    else:
        res = _error(ValueError(f"unknown git hook {hook!r}"))
    text = render_text(res, cfg.report.style, cfg.report.advisory_cap, cfg.report.max_chars)
    with contextlib.suppress(OSError):
        audit.append(
            cfg.root,
            res,
            audit.Event(harness="git", event=hook, elapsed_ms=int((time.monotonic() - t0) * 1000)),
        )
    return res, text


def script(binary: str, hook: str) -> str:
    return (
        "#!/bin/sh\n"
        "# Installed by `rulewarden init --git-hooks`. Do not bypass with --no-verify.\n"
        f'exec {shlex.quote(binary)} hook git {hook} "$@"\n'
    )


def install(root: Path, binary: str, hooks: tuple[str, ...] = HOOKS) -> list[Path]:
    hooks_dir = Path(gitsrc.git(root, "rev-parse", "--git-path", "hooks").strip())
    if not hooks_dir.is_absolute():
        hooks_dir = root / hooks_dir
    hooks_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for hook in hooks:
        p = hooks_dir / hook
        if p.exists() and "rulewarden" not in p.read_text(encoding="utf-8", errors="replace"):
            p.rename(p.with_name(hook + ".pre-rulewarden"))
        p.write_text(script(binary, hook), encoding="utf-8")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        written.append(p)
    return written


def default_binary(root: Path) -> str:
    venv = root / ".venv" / "bin" / "rulewarden"
    if venv.exists():
        return str(venv)
    found = [os.path.join(d, "rulewarden") for d in os.environ.get("PATH", "").split(os.pathsep)]
    for f in found:
        if os.access(f, os.X_OK):
            return f
    return "rulewarden"
