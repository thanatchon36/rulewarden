"""`rulewarden doctor`: installation, hook wiring, lock integrity, audit chain, determinism."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys

from rulewarden.config import Config
from rulewarden.engine import audit
from rulewarden.errors import RulewardenError

_ENVS = (
    {"TZ": "UTC", "LC_ALL": "C", "PYTHONHASHSEED": "0"},
    {"TZ": "Asia/Bangkok", "LC_ALL": "en_US.UTF-8", "PYTHONHASHSEED": "12345"},
    {"TZ": "America/Los_Angeles", "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "random"},
)


def determinism_selftest() -> tuple[bool, str]:
    digests = []
    for extra in _ENVS:
        env = {**os.environ, **extra}
        proc = subprocess.run(
            [sys.executable, "-m", "rulewarden.selftest"],
            capture_output=True,
            env=env,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            return (
                False,
                f"self-test process failed: {proc.stderr.decode('utf-8', 'replace').strip()[:300]}",
            )
        report = json.loads(proc.stdout)
        if report.get("status") != "blocked":
            return False, f"self-test produced an unexpected status {report.get('status')!r}"
        digests.append(hashlib.sha256(proc.stdout).hexdigest())
    if len(set(digests)) != 1:
        return False, "reports differ across processes: " + ", ".join(d[:12] for d in digests)
    return True, f"{len(digests)} processes, identical report sha256 {digests[0][:16]}"


def _hooks_wired(cfg: Config) -> list[str]:
    notes = []
    settings = cfg.root / ".claude" / "settings.json"
    if settings.exists():
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except ValueError:
            return ["FAIL .claude/settings.json is not valid JSON"]
        hooks = data.get("hooks", {})
        for ev in ("PreToolUse", "PostToolUse", "Stop", "SessionStart"):
            cmds = [h for g in hooks.get(ev, []) for h in g.get("hooks", [])]
            wired = [
                h
                for h in cmds
                if "rulewarden" in (h.get("command", "") + " ".join(h.get("args", [])))
            ]
            if not wired:
                notes.append(f"WARN Claude Code {ev} hook not wired to rulewarden")
            elif ev == "PreToolUse" and not all(h.get("onFailure") == "block" for h in wired):
                notes.append(
                    "WARN PreToolUse hook lacks onFailure: block (a crash would fail open)"
                )
            else:
                notes.append(f"ok   Claude Code {ev} hook wired")
    else:
        notes.append("info no .claude/settings.json (Claude Code adapter not installed)")
    pc = cfg.root / ".git" / "hooks" / "pre-commit"
    pcc = cfg.root / ".pre-commit-config.yaml"
    if pc.exists() and "rulewarden" in pc.read_text(encoding="utf-8", errors="replace"):
        notes.append("ok   git pre-commit hook wired")
    elif pcc.exists() and "rulewarden" in pcc.read_text(encoding="utf-8"):
        notes.append("ok   pre-commit framework config wired (run `pre-commit install`)")
    else:
        notes.append("WARN no git pre-commit hook runs rulewarden")
    return notes


def run_doctor(cfg: Config, determinism_only: bool = False) -> tuple[bool, list[str]]:
    lines: list[str] = []
    ok = True
    det_ok, det_msg = determinism_selftest()
    lines.append(f"{'ok  ' if det_ok else 'FAIL'} determinism self-test: {det_msg}")
    ok &= det_ok
    if determinism_only:
        return ok, lines
    lines.append(f"ok   python {sys.version.split()[0]}")
    lines.append("ok   git found" if shutil.which("git") else "FAIL git not on PATH")
    ok &= bool(shutil.which("git"))
    lines.append(
        "ok   jq found"
        if shutil.which("jq")
        else "info jq not on PATH (jq engine rules will fail closed)"
    )
    from rulewarden.engine.fixtures import qualify
    from rulewarden.engine.loader import load_rules
    from rulewarden.engine.lock import verify_lock

    try:
        rs = load_rules(cfg)
        lines.append(f"ok   {len(rs.rules)} rules load from {', '.join(cfg.rule_paths)}")
        rep = qualify(cfg, rs)
        lines.append(
            f"{'ok  ' if rep.passed else 'FAIL'} fixtures: {rep.summary()['fixtures']} run"
        )
        ok &= rep.passed
    except RulewardenError as exc:
        lines.append(f"FAIL rules do not load: {exc}")
        ok = False
    try:
        verify_lock(cfg)
        lines.append("ok   rules.lock matches the rule set")
    except RulewardenError as exc:
        lines.append(f"FAIL lock: {exc}")
        ok = False
    intact, n, msg = audit.verify_chain(cfg.root)
    lines.append(f"{'ok  ' if intact else 'FAIL'} audit log: {n} entries, {msg}")
    ok &= intact
    lines.extend(_hooks_wired(cfg))
    return ok, lines
