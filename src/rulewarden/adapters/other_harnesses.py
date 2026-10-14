"""Codex, Gemini CLI and OpenCode adapters: translate their hook JSON to the Claude Code handler.

Contracts verified 2026-10-14 (research/harness-apis.md). Only pre-tool events are mapped;
for the end-of-turn gate use the git hook and CI paths, which work with any agent.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from rulewarden.adapters import claude_code
from rulewarden.config import Config

_PATCH_FILE_RE = re.compile(r"^\*\*\* (Add|Update) File: (.+)$")


def _apply_patch_files(patch: str) -> list[tuple[str, str]]:
    """Files and added text from a Codex apply_patch envelope (added lines only)."""
    files: list[tuple[str, list[str]]] = []
    for line in patch.split("\n"):
        m = _PATCH_FILE_RE.match(line)
        if m:
            files.append((m.group(2).strip(), []))
        elif files and line.startswith("+") and not line.startswith("+++"):
            files[-1][1].append(line[1:])
    return [(p, "\n".join(lines) + "\n") for p, lines in files]


def codex(cfg: Config, payload: Mapping[str, Any]) -> claude_code.Reply:
    tool = str(payload.get("tool_name", ""))
    event = str(payload.get("hook_event_name", ""))
    if event == "PreToolUse" and tool == "apply_patch":
        cmd = str((payload.get("tool_input") or {}).get("command", ""))
        for path, added in _apply_patch_files(cmd):
            existing = claude_code._read(cfg, claude_code._rel(cfg, path)) or ""
            reply, _, _ = claude_code.handle(
                cfg,
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "tool_input": {"file_path": path, "content": existing + added},
                },
            )
            if reply.stdout:
                return reply
        return claude_code.Reply()
    reply, _, _ = claude_code.handle(cfg, payload)
    return reply


_GEMINI_TOOLS = {"run_shell_command": "Bash", "write_file": "Write", "replace": "Edit"}


def gemini(cfg: Config, payload: Mapping[str, Any]) -> claude_code.Reply:
    if payload.get("hook_event_name") != "BeforeTool":
        return claude_code.Reply()
    tool = _GEMINI_TOOLS.get(str(payload.get("tool_name", "")))
    if tool is None:
        return claude_code.Reply()
    tool_input = dict(payload.get("tool_input") or {})
    if tool == "Edit" and tool_input.get("allow_multiple"):
        tool_input["replace_all"] = True
    reply, _, _ = claude_code.handle(
        cfg, {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
    )
    if not reply.stdout:
        return claude_code.Reply()
    reason = json.loads(reply.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    return claude_code.Reply(json.dumps({"decision": "deny", "reason": reason}, ensure_ascii=False))


_OPENCODE_TOOLS = {"bash": "Bash", "write": "Write", "edit": "Edit"}


def opencode(cfg: Config, payload: Mapping[str, Any]) -> claude_code.Reply:
    """Input: {"tool": name, "args": {...}} from the JS plugin; output: {"block": bool, "reason": str}."""
    tool = _OPENCODE_TOOLS.get(str(payload.get("tool", "")))
    if tool is None:
        return claude_code.Reply(json.dumps({"block": False}))
    args = dict(payload.get("args") or {})
    tool_input = {
        "command": args.get("command", ""),
        "file_path": args.get("filePath", args.get("file_path", "")),
        "content": args.get("content", ""),
        "old_string": args.get("oldString", args.get("old_string", "")),
        "new_string": args.get("newString", args.get("new_string", "")),
        "replace_all": bool(args.get("replaceAll", False)),
    }
    reply, _, _ = claude_code.handle(
        cfg, {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
    )
    if not reply.stdout:
        return claude_code.Reply(json.dumps({"block": False}))
    reason = json.loads(reply.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    return claude_code.Reply(json.dumps({"block": True, "reason": reason}, ensure_ascii=False))


OPENCODE_PLUGIN = """// Installed by `rulewarden init --opencode`. Blocks tool calls that rulewarden rejects.
import { spawnSync } from "node:child_process";

export const Rulewarden = async ({ directory }) => ({
  "tool.execute.before": async (input, output) => {
    const res = spawnSync("{bin}", ["hook", "opencode"], {
      cwd: directory,
      input: JSON.stringify({ tool: input.tool, args: output.args }),
      encoding: "utf-8",
      timeout: 60000,
    });
    let verdict;
    try {
      verdict = JSON.parse(res.stdout || "");
    } catch {
      throw new Error("rulewarden: hook failed; failing closed. " + (res.stderr || ""));
    }
    if (verdict.block) throw new Error(verdict.reason);
  },
});
"""
