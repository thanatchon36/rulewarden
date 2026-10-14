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
- [x] Stop is a warning gate (ADR-011); repo rule config and lockout incident recorded (ADR-010); locked rule inputs exempt from content rules, synthetic targets need explicit selection (ADR-012). Committed 014a1ae; all three git hooks passed
- [x] `make check` green: 135 tests, coverage 92%, ruff, mypy --strict, test-rules (repo + shipped), determinism,
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
- [x] `rulewarden init`: agent hooks only with `--lock`, between two lock writes; `--hooks-only` (ADR-013)
- [x] `doctor` fails when agent hooks are installed without a valid lock
- [x] Contract tests per harness: Claude Code (4 events, Stop gate), git hooks (incl. a real `git commit`), CI,
      Codex, Gemini, OpenCode (`tests/test_adapters.py`); live evidence: this session runs under the Claude Code hooks
- [x] `docs/integrations.md` (setup order, per-harness behaviour, pre-commit and GitHub Actions examples)
- [x] `research/harness-apis.md`: mid-session settings reload observed
- [ ] `.pre-commit-hooks.yaml` consumer manifest — NEEDS_HUMAN H5 (outside SCP-001 allowed paths)
- [ ] Live Claude Code demo (block + self-correct) for the README — recorded in Phase 5 with the benchmark runner
## Phase 4 — Corpus
- [x] Collected 300 files (60 per stratum, OSI-licensed only) on 2026-10-14 → `corpus/data/files.csv`
- [x] 3,844 rule-like lines extracted with the `compile` extractor, scrubbed → `rules.csv`
- [x] Rubric labels (`corpus/label.py`, pinned by `tests/test_corpus_rubric.py`) and two model passes (Haiku 5.5,
      fixed prompt, raw responses in `corpus/data/model_raw/`)
- [x] Analysis with file-cluster bootstrap CIs and κ → `summary.json`, `paper/tables/corpus_*.md`, figures
- [x] Paper §4 written with generated numbers (`paper/render.py` fills placeholders; unresolved = build failure)
- Finding: rubric and model disagree on decidability (κ ≈ 0.09). Deterministic share is 19% (model) to 34% (rubric),
  9% by both; shipped compile templates match about 5% of lines.
## Phase 5 — Benchmark
- [x] 20 validated tasks; harness; replay (no API key); analysis plan frozen in 2593565 before the first non-pilot run
- [x] 150/150 runs used: 1 pilot + 149 (A 20, B 50, C 49, D 20, E 10); 0 infrastructure failures; replay 0 mismatches
- [x] Result: ceiling in every condition (0 final-diff violations, 100% hidden-test success); H1–H6 null; RQ5 0 attempts
- [x] Hooks caught 13 genuine violations mid-session (B-DOCSTRING), all self-corrected; 29 blocks were the A1 false
      positive (B-TESTS-RO on files the agent created itself). The defect was fixed after the last run (ADR-015)
- [x] RQ3: 28/28 safety-property tests pass; hook latency p50 PreToolUse 9 ms, PostToolUse 51 ms, Stop 53 ms
## Phase 6 — Paper
## Phase 7 — Hardening, verification, release prep
