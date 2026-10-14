# Harness hook APIs — verified contracts

Verified 2026-10-14 against the official docs and, for Claude Code, the installed binary (`claude --version` →
`2.1.299`). Adapters in `src/rulewarden/adapters/` implement exactly what is written here. If a harness changes its
contract, update this file first, then the adapter and its contract test.

## Claude Code (primary)

Source: <https://code.claude.com/docs/en/hooks> (markdown at `…/hooks.md`), retrieved 2026-10-14.

- **Config**: `.claude/settings.json` → `hooks.<Event>[] = {matcher, hooks: [{type: "command", command, args?, timeout?, onFailure?}]}`.
  Matchers are regexes over tool name (`"Edit|Write"`). `${CLAUDE_PROJECT_DIR}` is available in commands.
- **Input**: one JSON object on stdin. Common fields: `session_id`, `transcript_path`, `cwd`, `permission_mode`,
  `hook_event_name`. Tool events add `tool_name`, `tool_input`, `tool_use_id`. PostToolUse adds `tool_response`.
  Stop adds `stop_hook_active`, `last_assistant_message`. SessionStart adds `source` (`startup|resume|clear|compact|fork`).
- **Tool inputs**: `Bash{command, description?, timeout?, run_in_background?}`, `Write{file_path (absolute), content}`,
  `Edit{file_path (absolute), old_string, new_string, replace_all?}`. **`MultiEdit` no longer appears in the reference**,
  so we match `Edit|Write|NotebookEdit`.
- **Exit codes**: `0` success (stdout parsed as JSON if it is exactly one JSON object). `2` blocking error (stderr is the
  reason; on PreToolUse it blocks the call). Any other code is a **non-blocking error**: the action proceeds.
  ⇒ Enforcement must use exit 0 + JSON decision, or exit 2. Exit 1 is fail-open in Claude Code.
- **`onFailure: "block"`** (v2.1.295+) on a command hook: crash, timeout, non-0/2 exit or invalid JSON → behaves like exit 2.
  **This is how rulewarden gets fail-closed (P5) at the harness level.** Not honoured on Stop (exit 2 there means "keep working").
- **Timeouts**: default 600 s for command hooks. On PreToolUse a timed-out hook does **not** block unless `onFailure: "block"`.
- **Decisions**:
  - PreToolUse: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "…"}}`.
    The reason is shown to Claude. Precedence across hooks: deny > defer > ask > allow.
  - PostToolUse: top-level `{"decision": "block", "reason": "…"}`. The reason is placed next to the tool result. The tool
    **already ran**, so this is feedback, not prevention.
  - Stop: `{"decision": "block", "reason": "…"}` prevents stopping. Loop guard: `stop_hook_active`, and an
    **8-consecutive-continuation cap** (override with `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`).
  - SessionStart: context only (`additionalContext`). Cannot block.
- **Output caps**: `additionalContext` / `systemMessage` / plain stdout are capped at **10,000 characters**. Above that,
  Claude sees a file path and a 2,000-character preview. Our P7 hook-message cap (2,000 chars default) stays well below.
- **Bash edits**: PostToolUse for Bash may carry `tool_response.bashEditDiff` (beta, best-effort; docs say not to
  enforce on it). We therefore compute the diff ourselves from git.
- **Settings reload**: the docs do not promise that hooks added to `.claude/settings.json` mid-session take effect in a
  running session. We record empirically what happened in this repository (see `STATUS.md`).

## Codex CLI (Could)

Source: <https://developers.openai.com/codex/hooks> (markdown at `…/hooks.md`), retrieved 2026-10-14.

- Config: `<repo>/.codex/hooks.json` or inline `[hooks]` in `.codex/config.toml`. Project hooks load only when the
  project `.codex/` layer is **trusted**.
- Events: `SessionStart`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `UserPromptSubmit`, `Stop`, … — same shape as Claude Code.
- Tool coverage: shell (`Bash`), `apply_patch` (matchable as `apply_patch|Edit|Write`; `tool_input.command` holds the
  patch text), MCP tools. Docs: *"Treat tool hooks as a useful guardrail, not a complete enforcement boundary."*
- Deny: `hookSpecificOutput.permissionDecision: "deny"` + reason, or legacy `{"decision":"block"}`, or exit 2 + stderr.
  Callback errors/timeouts in `PreToolUse` are fail-open (docs, "Managed hooks" section).

## Gemini CLI (Could)

Source: <https://github.com/google-gemini/gemini-cli/blob/main/docs/hooks/reference.md> and `docs/reference/tools.md`,
retrieved 2026-10-14 (installed CLI 0.36.0).

- Config: `settings.json` → `hooks.BeforeTool[] = {matcher (regex), hooks: [{type: "command", command, timeout (ms)}]}`.
- `BeforeTool` input: `tool_name`, `tool_input`. Tools: `write_file{file_path, content}`, `replace{file_path, old_string,
  new_string, …}`, `run_shell_command{command, …}`.
- Block: exit 0 + `{"decision": "deny", "reason": "…"}`, or exit 2 + stderr. Other exit codes are warnings (fail-open).
  `AfterAgent` with `decision: "deny"` forces a retry (Stop analogue).

## OpenCode (Should)

Source: <https://opencode.ai/docs/plugins> (source `packages/web/src/content/docs/plugins.mdx`), retrieved 2026-10-14.

- JS/TS plugins in `.opencode/plugins/` are loaded at startup. A plugin returns hooks such as
  `"tool.execute.before": async (input, output) => {…}`. `input.tool` is the tool name and `output.args` the arguments.
  **Throwing an Error blocks the tool call**, and the message goes back to the agent.
- Our adapter is a small JS plugin that shells out to `rulewarden hook opencode` with the same JSON on stdin.

## Universal fallbacks

- **git hooks** (`.git/hooks/pre-commit`, `pre-push`): exit non-zero aborts. Bypassable with `--no-verify`, which is why
  the Claude Code PreToolUse adapter blocks `--no-verify` and CI re-runs the check.
- **pre-commit framework** [pre-commit.com]: `.pre-commit-config.yaml` with a `repo: local` hook running
  `rulewarden check --staged`.
- **CI**: `rulewarden check --base origin/main` in GitHub Actions. This is the final, unbypassable-by-the-agent gate.
