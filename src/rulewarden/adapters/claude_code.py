"""Claude Code hook adapter (contract: research/harness-apis.md, verified 2026-10-14).

One entry point for all events; the event comes from `hook_event_name` on stdin.
PreToolUse denies before actuation (Simplex); PostToolUse feeds back on the tree;
Stop is a warning gate (ADR-011): git hooks and CI remain the fail-closed gates.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rulewarden.config import CONFIG_DIR, Config
from rulewarden.engine import audit, gitsrc
from rulewarden.engine.diff import Diff, diff_between
from rulewarden.engine.globs import match_any
from rulewarden.engine.report import EXIT_PASS, Finding, Result, ordered, render_text
from rulewarden.engine.runner import Request, _synthetic, run_check
from rulewarden.errors import RulewardenError

EDIT_TOOLS = frozenset({"Edit", "Write", "NotebookEdit", "MultiEdit"})
STATE_DIR = f"{CONFIG_DIR}/tmp"
NEEDS_HUMAN_FILE = "NEEDS_HUMAN.md"
INFRA_IDS = frozenset({"RW-LOCK", "RW-LOAD", "RW-BUDGET", "RW-DIFF"})


@dataclass(frozen=True)
class Reply:
    stdout: str = ""
    exit_code: int = 0
    outcome: str = ""


def _render(result: Result, cfg: Config) -> str:
    return render_text(result, cfg.report.style, cfg.report.advisory_cap, cfg.report.max_chars)


def _rel(cfg: Config, file_path: str) -> str:
    p = Path(file_path)
    if not p.is_absolute():
        p = cfg.root / p
    try:
        return p.resolve().relative_to(cfg.root.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def _read(cfg: Config, rel: str) -> str | None:
    p = cfg.root / rel
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def proposed_content(
    cfg: Config, tool: str, tool_input: Mapping[str, Any]
) -> tuple[str, str | None, str | None]:
    """(relative path, current content, proposed content) for an edit tool call."""
    path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
    rel = _rel(cfg, path)
    old = _read(cfg, rel)
    if tool == "Write":
        return rel, old, str(tool_input.get("content", ""))
    if tool == "Edit":
        before = str(tool_input.get("old_string", ""))
        after = str(tool_input.get("new_string", ""))
        if old is None or before not in old:
            return rel, old, old
        count = -1 if tool_input.get("replace_all") else 1
        return rel, old, old.replace(before, after, count)
    if tool == "MultiEdit":
        cur = old
        for e in tool_input.get("edits", []) or []:
            if cur is None or e.get("old_string", "") not in cur:
                continue
            count = -1 if e.get("replace_all") else 1
            cur = cur.replace(e["old_string"], e.get("new_string", ""), count)
        return rel, old, cur
    # NotebookEdit: cell-level JSON edits; evaluate the cell source as the proposed addition.
    return rel, old, str(tool_input.get("new_source", ""))


def _new_since_baseline(cfg: Config, rel: str) -> bool:
    """True if `rel` was created after the session baseline (absent there, not pre-existing untracked)."""
    session = gitsrc.load_session(cfg.root)
    untracked = session.get("untracked")
    if isinstance(untracked, dict) and rel in untracked:
        return False
    base = str(session.get("baseline") or cfg.baseline)
    try:
        base = gitsrc.resolve_base(cfg.root, base)
        found = gitsrc.git(cfg.root, "ls-tree", "--name-only", base, "--", rel, check=False)
    except RulewardenError:
        return False
    return not found.strip()


def _deny(reason: str) -> Reply:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    return Reply(json.dumps(out, ensure_ascii=False))


def _state_path(cfg: Config, name: str) -> Path:
    return cfg.root / STATE_DIR / name


def _changed_since_last(cfg: Config, key: str, text: str) -> bool:
    p = _state_path(cfg, key)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    try:
        if p.exists() and p.read_text(encoding="utf-8").strip() == digest:
            return False
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(digest + "\n", encoding="utf-8")
    except OSError:
        return True
    return True


def _worktree(cfg: Config) -> tuple[Diff | None, Result]:
    try:
        diff = gitsrc.worktree_diff(cfg)
    except RulewardenError as exc:
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
        return None, res
    return diff, run_check(cfg, Request(diff=diff))


def _worktree_result(cfg: Config) -> Result:
    return _worktree(cfg)[1]


def _fixable(cfg: Config, diff: Diff | None, f: Finding) -> bool:
    """True when the agent introduced this finding this session and is allowed to fix it."""
    if not f.blocking or f.rule_id in INFRA_IDS or f.kind == "error" or diff is None:
        return False
    if not f.path or match_any(f.path, cfg.protected_paths):
        return False
    fc = diff.by_path().get(f.path)
    if fc is None:
        return False
    return f.line is None or fc.status == "added" or f.line in fc.added_line_numbers


def _record_needs_human(cfg: Config, findings: list[Finding]) -> None:
    path = cfg.root / NEEDS_HUMAN_FILE
    try:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        new = [f"- [ ] Stop gate (unresolved): {f.render()}" for f in ordered(findings)]
        new = [ln for ln in dict.fromkeys(new) if ln not in current]
        if not new:
            return
        prefix = current if not current or current.endswith("\n") else current + "\n"
        path.write_text(prefix + "\n".join(new) + "\n", encoding="utf-8")
    except OSError:
        return


def _stop(cfg: Config, payload: Mapping[str, Any]) -> tuple[Reply, Result]:
    """Warning gate (ADR-011): block only on fixable findings, never twice in a row."""
    diff, res = _worktree(cfg)
    blocking = [f for f in res.findings if f.blocking]
    if not blocking:
        return Reply(), res
    if payload.get("stop_hook_active"):
        _record_needs_human(cfg, blocking)
        msg = "rulewarden: stopping with unresolved findings (recorded in NEEDS_HUMAN.md).\n"
        out = {"systemMessage": msg + _render(res, cfg)}
        return Reply(json.dumps(out, ensure_ascii=False), outcome="stop_unresolved"), res
    fixable = [f for f in res.findings if _fixable(cfg, diff, f)]
    if fixable:
        reason = "rulewarden: cannot finish — fix the findings introduced this session.\n"
        sub = Result(findings=fixable)
        out = {"decision": "block", "reason": reason + _render(sub, cfg)}
        return Reply(json.dumps(out, ensure_ascii=False), outcome="stop_blocked"), res
    msg = "rulewarden: findings outside this session's fixable scope (not blocking Stop).\n"
    out = {"systemMessage": msg + _render(res, cfg)}
    return Reply(json.dumps(out, ensure_ascii=False), outcome="stop_reported"), res


def handle(cfg: Config, payload: Mapping[str, Any]) -> tuple[Reply, Result | None, str]:
    event = str(payload.get("hook_event_name", ""))
    tool = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, Mapping):
        tool_input = {}

    if event == "SessionStart":
        gitsrc.record_session(cfg.root, str(payload.get("session_id", "")))
        return Reply(), None, event

    if event == "PreToolUse":
        if tool == "Bash":
            res = run_check(cfg, Request(command=str(tool_input.get("command", ""))))
            if res.exit_code != EXIT_PASS:
                return _deny("rulewarden blocked this command.\n" + _render(res, cfg)), res, event
            return Reply(), res, event
        if tool in EDIT_TOOLS:
            rel, old, new = proposed_content(cfg, tool, tool_input)
            if old is not None and new is not None and _new_since_baseline(cfg, rel):
                old = None
            fc = diff_between(rel, old, new)
            res = run_check(
                cfg,
                Request(
                    diff=Diff(
                        files=[fc],
                        raw_sha256=hashlib.sha256(
                            (rel + "\0" + (new or "")).encode("utf-8")
                        ).hexdigest(),
                    ),
                    check_protected_drift=False,
                ),
            )
            if res.exit_code != EXIT_PASS:
                return (
                    _deny(
                        "rulewarden rejected this edit; nothing was written.\n" + _render(res, cfg)
                    ),
                    res,
                    event,
                )
            return Reply(), res, event
        return Reply(), None, event

    if event == "Stop":
        reply, res = _stop(cfg, payload)
        return reply, res, event

    if event == "PostToolUse":
        res = _worktree_result(cfg)
        text = _render(res, cfg)
        if res.exit_code != EXIT_PASS:
            out_block = {"decision": "block", "reason": text}
            return Reply(json.dumps(out_block, ensure_ascii=False)), res, event
        if res.findings and _changed_since_last(cfg, "post-advisory", text):
            out = {
                "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}
            }
            return Reply(json.dumps(out, ensure_ascii=False)), res, event
        return Reply(), res, event

    return Reply(), None, event


def main(cfg: Config, stdin_text: str) -> Reply:
    t0 = time.monotonic()
    try:
        payload = json.loads(stdin_text or "{}")
        if not isinstance(payload, dict):
            raise ValueError("hook input is not a JSON object")
    except ValueError as exc:
        # Unreadable input: fail closed for tool calls (exit 2 blocks PreToolUse).
        return Reply(f"rulewarden: unreadable hook input ({exc}); failing closed", 2)
    reply, res, event = handle(cfg, payload)
    if res is not None:
        with contextlib.suppress(OSError):
            audit.append(
                cfg.root,
                res,
                audit.Event(
                    harness="claude-code",
                    event=event
                    + (f":{payload.get('tool_name')}" if payload.get("tool_name") else ""),
                    session_id=str(payload.get("session_id", "")),
                    elapsed_ms=int((time.monotonic() - t0) * 1000),
                    outcome=reply.outcome,
                ),
            )
    return reply


SETTINGS_TEMPLATE: dict[str, Any] = {
    "hooks": {
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "{bin}",
                        "args": ["hook", "claude-code", "--root", "${CLAUDE_PROJECT_DIR}"],
                        "timeout": 30,
                    }
                ]
            }
        ],
        "PreToolUse": [
            {
                "matcher": "Bash|Edit|Write|NotebookEdit|MultiEdit",
                "hooks": [
                    {
                        "type": "command",
                        "command": "{bin}",
                        "args": ["hook", "claude-code", "--root", "${CLAUDE_PROJECT_DIR}"],
                        "timeout": 60,
                        "onFailure": "block",
                    }
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Bash|Edit|Write|NotebookEdit|MultiEdit",
                "hooks": [
                    {
                        "type": "command",
                        "command": "{bin}",
                        "args": ["hook", "claude-code", "--root", "${CLAUDE_PROJECT_DIR}"],
                        "timeout": 60,
                        "onFailure": "block",
                    }
                ],
            }
        ],
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "{bin}",
                        "args": ["hook", "claude-code", "--root", "${CLAUDE_PROJECT_DIR}"],
                        "timeout": 120,
                    }
                ]
            }
        ],
    }
}


def settings_for(binary: str) -> dict[str, Any]:
    text = json.dumps(SETTINGS_TEMPLATE).replace(
        "{bin}", binary.replace("\\", "\\\\").replace('"', '\\"')
    )
    data: dict[str, Any] = json.loads(text)
    return data


def merge_settings(existing: dict[str, Any], binary: str) -> dict[str, Any]:
    """Add rulewarden hooks to existing settings without removing anything else."""
    ours = settings_for(binary)["hooks"]
    out = dict(existing)
    hooks = dict(out.get("hooks", {}))
    for event, groups in ours.items():
        current = [
            g
            for g in hooks.get(event, [])
            if not any("rulewarden" in json.dumps(h) for h in g.get("hooks", []))
        ]
        hooks[event] = current + groups
    out["hooks"] = hooks
    return out
