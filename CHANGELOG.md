# Changelog

All notable changes to this project are documented here. The format follows Keep a Changelog, and the project uses
semantic versioning.

## [Unreleased] — 0.1.0

### Added
- Deterministic rule engine: YAML schema with severity (advisory/required/critical) and decidability
  (deterministic/heuristic/undecidable) tiers; engines `regex` (ReDoS-screened), `glob`, `ast`, `jq`, `shell`
  (opt-in, sandboxed) and `python` plugins; bounded execution with a forked watchdog; fail-closed on engine errors
  for blocking rules.
- `rules.lock`: SHA-256 of rule files and protected paths, written only by a human `rulewarden lock` and only when
  every fixture passes.
- Alarm-managed reports (severity first, deduplicated, capped, one `Fix:` per finding) and canonical JSON.
- Deviations with approvers and expiry; agent-authored deviations of blocking rules are critical findings.
- Hash-chained audit log, `report` (including `--framework nist-ai-rmf`) and `stats`.
- Adapters: Claude Code (PreToolUse, PostToolUse, Stop, SessionStart), git hooks (pre-commit, commit-msg,
  pre-push), pre-commit framework, CI with GitHub annotations, Codex, Gemini CLI, OpenCode.
- `compile`: template-based conversion of instruction files, with a report of uncompilable lines.
- `init` (installs agent hooks only together with a lock), `doctor` (wiring, lock, audit chain, determinism).
- Seven starter packs, 26 rules, 120 fixtures.

### Changed
- The Claude Code Stop hook is a warning gate: it blocks only on findings the agent introduced and may fix, and never
  blocks twice in a row (ADR-011).
- Locked rule files are exempt from content rules, and synthetic targets such as `:commit-msg` need explicit
  selection (ADR-012).

### Known issues
- The PreToolUse adapter evaluates path-status rules against the file on disk rather than the session baseline, so
  editing a test file the agent created in the same session is reported as modifying an existing test (benchmark
  amendment A1). It was left unfixed while the benchmark ran, to keep the treatment constant.
- PRT-002's protected-path pattern also matches nested directories named `rules/` (NEEDS_HUMAN H6).
- Command rules match command text, so a heredoc that quotes a protected command is denied (ADR-013).
