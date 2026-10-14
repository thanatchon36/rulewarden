# STATUS.md

Resume: read `MISSION.md`, this file and `DECISIONS.md`, then continue from the first unchecked item.

## Phase 0 — Setup
- [x] Name chosen: `rulewarden` (ADR-001)
- [x] git init, LICENSE (Apache-2.0), pyproject, uv env, Makefile stub, CI skeleton
- [x] CLAUDE.md / AGENTS.md = Appendix A
- [x] STATUS / DECISIONS / NEEDS_HUMAN, research/, paper/ skeleton
- [x] GitHub repo (private, ADR-004) + first push

## Phase 1 — Research sprint
- [x] research/evidence.md (§2 leads verified; HN lead corrected, ADR-007)
- [x] research/related-work.md (14 tools, 8 empirical papers; refs verified 58/59, ADR-008)
- [x] research/harness-apis.md (Claude Code 2.1.299 contract incl. onFailure:block; Codex, Gemini, OpenCode)
- [x] bench/ANALYSIS_PLAN.md draft (freeze before first run); corpus/README.md query plan
- [x] paper Background + Related work drafts (paper/main.md)

## Phase 2 — Core engine
- [x] Engine: schema, loader, lock, runner, report, audit (hash-chained), bounded fork watchdog, ReDoS screen,
      diff/gitsrc, deviations, fixtures; checks regex/glob/ast/jq/shell/python (ADR-009)
- [x] 7 packs, 26 rules, 120 fixtures; compiler; adapters (Claude Code, git hooks, CI, other harnesses); CLI
- [x] Repo enforcement files; human lock done 2026-10-14 (26 rules, 13 protected files); git hooks installed
- [x] Stop is a warning gate (ADR-011); repo rule config and lockout incident recorded (ADR-010)
- [x] `make check` green: 132 tests, coverage 92%, ruff, mypy --strict, test-rules (repo + shipped), determinism,
      self-check PASS

Incident log (dogfooding evidence, paper §6), 2026-10-14:
1. The agent wrote `.claude/settings.json` before the lock. Hooks loaded mid-session, and every tool call was denied
   with RW-LOCK. Stop looped up to the continuation cap.
2. Lock attempts 1 and 2 failed `test-rules` (PRT-001 fixture vs `protected: [".claude/**"]`).
3. The agent proposed disabling its own hooks. The human renamed `settings.json`, which opened an **unmonitored
   window**: the agent edited `engine/audit.py` and `adapters/claude_code.py`, which were not audited.
4. A reviewer flagged the proposal. The human restored the hooks, fixed the fixture and locked.
5. After the lock, PRT-003 correctly denied a Bash heredoc whose ADR text quoted a human-only command (a false
   positive on quoted text, the expected price of command-string matching). The ADR was written with Edit instead.

## Phase 3 — Adapters
- [ ] `rulewarden init`: write and require the lock before installing harness hooks (lesson from ADR-010)
## Phase 4 — Corpus
## Phase 5 — Benchmark
## Phase 6 — Paper
## Phase 7 — Hardening, verification, release prep
