# FINAL_REPORT

Mission: `MISSION.md` (Phases 0–7). Date: 2026-10-14. Repository: `thanatchon36/rulewarden` (private).
Stop reason: the Definition of Done (§11) is met except for the items that need a human (push, public repository,
PyPI). The benchmark budget (`BENCH_MAX_RUNS=150`) was used in full.

## Definition of Done (§11)

| Item | Status |
|---|---|
| `make check` green on a clean clone (Linux and macOS in CI) | Yes: locally, on a clean clone (verifier), and in CI run 38540593133 (Ubuntu and macOS × Python 3.11/3.12, plus the paper job) |
| Determinism, fail-closed and fixture suites pass; every shipped rule has fixtures | Yes (26 rules, 120 fixtures; RQ3 28/28) |
| Claude Code hook blocks a required violation and the agent self-corrects (README) | Yes, recorded in `bench/recorded/T01-slugify/C-r1` and quoted in the README |
| pre-commit/git hook path works with no harness | Yes (`test_real_git_commit_is_blocked`; verifier's real commit was refused) |
| Corpus results with n and labelling method | Yes (§4: n = 300 files, 3,844 lines; rubric plus two model passes) |
| Benchmark B vs C on ≥10 tasks, recordings, key-free `replay.py` | Yes (20 tasks; 149 runs; 0 replay mismatches) |
| Paper builds from scripts; numbers traceable; references verified; limitations; fair competitors | Yes (`make paper`; 58/59 references) |
| The repo's audit log shows enforcement during development | Yes (Appendix A; 600+ entries, chain intact) |
| Independent verifier found no unfixed bypass | Yes, after fixes (ADR-016) |
| FINAL_REPORT, NEEDS_HUMAN, CHANGELOG written; committed and pushed; PyPI left to the human | Yes: pushed by the human at 9ca58ee (H4); PyPI left to the human (H3) |

## What shipped

- **rulewarden 0.1.0** (Apache-2.0): a deterministic, fail-closed rule engine. It has 6 check engines, a
  human-only lock that records rule-file and protected-path hashes, fixture qualification, alarm-managed reports,
  deviations with approvers, a hash-chained audit log, and `report`, `stats` and `doctor`.
- **Adapters**: Claude Code (4 events; Stop is a warning gate), git hooks, pre-commit framework, CI (GitHub
  annotations), Codex, Gemini CLI, OpenCode. `init` installs agent hooks only together with a lock.
- **Seven starter packs**: 26 rules, 120 fixtures. `compile` turns instruction files into rules and reports the
  lines it could not compile.
- **Corpus study (RQ1)**: 300 OSI-licensed instruction files, 3,844 rule-like lines, rubric labels plus two model
  passes, all labels and raw responses published.
- **Benchmark (RQ2–RQ5)**: 20 validated tasks; plan frozen before the first non-pilot run; 149 runs plus 1 pilot;
  all recordings committed; `bench/replay.py` recomputes every number with no API key (0 mismatches).
- **Paper** (`paper/main.md` → `make paper`): every number is rendered from generated results, and the build fails on
  an unresolved number or an unverified citation (58/59 references verified).
- **Docs**: README (with a recorded block-and-correct demo), `docs/integrations.md`, `docs/security.md`, CHANGELOG,
  DECISIONS (ADR-001–016), STATUS.

## Key results

- **RQ1**: only a minority of rules are deterministically checkable on a diff: 19% (model) to 34% (rubric), and 9% by
  both. The labellers barely agree (κ ≈ 0.09). Shipped `compile` templates match about 5% of lines.
- **RQ2/RQ4/RQ5**: ceiling. No condition, including the one without rules, left a violation in the final diff, and
  all runs passed their hidden tests. The pre-registered tests are null. Hook cost was small (median +0.6 turns,
  +2 s per task, not significant).
- **What the hooks saw**: 13 genuine docstring violations denied before they were written, all self-corrected. 29
  false-positive blocks came from a rulewarden defect (amendment A1), which was kept frozen during the benchmark
  and fixed afterwards.
- **RQ3**: 28/28 safety-property tests pass. Hook latency p50: PreToolUse 9 ms, PostToolUse 50 ms, Stop 52 ms.

## What was cut or not done, and why

- **P11 (STPA guide)**: not written (MoSCoW Could, v3, documentation only).
- **Benchmark stage 6**: 19 of 40 runs (budget). E covered 10 tasks, as planned.
- **Human corpus labels**: none (no human labeller available). The paper states that labels are rubric-based and
  model-assisted.
- **OpenCode/Codex/Gemini adapters**: contract-tested against their documented JSON, not exercised live.
- **PDF**: the paper builds to HTML (pandoc). No LaTeX engine is installed.

## Budget used

| Budget | Limit | Used |
|---|---|---|
| Benchmark agent runs | 150 | 150 (1 pilot + 149) |
| Corpus files | 300 | 300 |
| Money | $0 | $0 (model labelling and runs under the session's subscription; ADR-014) |

## Incidents (dogfooding evidence)

1. **Bootstrap lockout** (ADR-010). Hooks were installed before a lock existed, so every tool call was denied. The
   agent then proposed disabling its own monitor; the human did so and later restored it. This is recorded as the
   paper's central discussion point.
2. **Live-hook self-lockout** (ADR-015). A broken edit to the engine crashed the running hook, and fail-closed denied
   the next edit.
3. **Defects found by running on itself**: SH-002 self-match, the `:commit-msg` catch-all, quoted-text command false
   positives, unscannable transcripts (all fixed or recorded); A1 found by the benchmark (fixed); a jq binary
   resolvable from inside the repository, found in the security review (fixed); two bypasses found by the
   independent verifier (fixed, ADR-016).

## Independent verification (Phase 7)

A fresh general-purpose subagent, given only the clone path and the mission's verification instruction, ran from a
clean clone of `9cdacbd`.

- **Build:** `make check`, `make paper-ci` and `bench/replay.py --check` all passed.
- **Blocked or detected:** rule, lock and approver edits, `--no-verify`, `core.hooksPath` redirection and history
  rewrites (session hook); a violating commit (git hook); `rulewarden lock` without a TTY; an agent-authored
  deviation (RW-DEVIATION); oversized or invalid-UTF-8 files (fail closed as unverifiable); 3,000- and 8,000-file
  diffs (blocked; the 8,000-file diff exceeded the time budget, which is a known issue).
- **Defects found and fixed (ADR-016):**
  1. A NUL byte or UTF-16 encoding hid a credential from SEC-001 in staged, working-tree, git-hook and range checks.
  2. A bare `--diff` editing protected files was exempted when the disk matched the lock.
- **Re-verification at `0980174`:** both fixed. The residual UTF-32 miss was then fixed too. Remaining design limits
  (compressed or base64 secrets, keys split by NUL) are documented.
- **Bypass status:** no known unfixed bypass of a required rule within the threat model. The verifier could not test
  the lower layers against protected-file edits, because the session hook denied those writes first, and it did not
  try to get around that hook.

## Needs a human (NEEDS_HUMAN.md)

H1 confirm the name · H2 make the repository public · H3 PyPI release · H4 push the local commits · H5 pre-commit
consumer manifest · H6 anchor the PRT-002 path pattern · H7 run the hooks from a pinned install.
