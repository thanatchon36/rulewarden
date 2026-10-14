# MISSION.md — `<name>`: Deterministic Runtime Assurance for AI Coding Agents

> **Software 50 % · Paper 50 %.** Built end-to-end by Claude Code from this brief.
> Owner: Thanatchon Chongmankhong (github.com/thanatchon36) · License: Apache-2.0 · Language: English (code, docs, paper).
> `<name>` is a placeholder until Phase 0 picks the real name (Appendix C). Keep this file verbatim in the repo root.

---

## 0. How to run this mission

**Kickoff prompt (paste into Claude Code in an empty directory):**

```
Read MISSION.md completely before doing anything else. Then execute Phases 0–7 end to end
without pausing for approval. You are the only engineer, researcher and author on this project.
Never ask me questions: when a decision is needed, choose the safest reversible option, record it
in DECISIONS.md, and continue. Anything that is irreversible, costs money beyond the budget, or
has legal exposure goes into NEEDS_HUMAN.md — then keep working on everything else.
Keep STATUS.md current so a fresh session can resume from it. Commit at every checkpoint.
Stop only when the Definition of Done (§11) is met or a budget in §0.2 is exhausted; either way,
finish by writing FINAL_REPORT.md.
```

**Resume prompt (any later session):** `Read MISSION.md, STATUS.md and DECISIONS.md, then continue from the first unchecked item in STATUS.md.`

### 0.1 Operating mode
- Autonomous. No questions to the human. Decisions → `DECISIONS.md` (ADR style: context, options, choice, reversibility).
- Work only inside the project directory. Containment is a safety property, not a convenience.
- Every phase ends with: `make check` green → `STATUS.md` updated → commit (Conventional Commits).
- A fresh session must be able to resume from `STATUS.md` + `DECISIONS.md` alone. Write them for that reader.

### 0.2 Budgets (edit before kickoff if needed)
| Budget | Default | On exhaustion |
|---|---|---|
| Agent-under-test runs for the benchmark (§6.3) | `BENCH_MAX_RUNS=150` | Stop launching runs; report partial design with n per cell; replay still works |
| Wall-clock per phase (soft) | Phase 2: 6 h · Phase 5: 8 h · Phase 6: 6 h · others: 3 h | Cut scope by MoSCoW (§10.1); never cut tests, fixtures, or determinism checks |
| Corpus files fetched (§6.2) | `CORPUS_MAX_FILES=300` | Analyse what was collected; state n |
| Money | $0 beyond the subscription that runs this session | Anything with a price tag → `NEEDS_HUMAN.md` |

### 0.3 Fixed decisions (do not relitigate)
- Python ≥ 3.11, `uv` for env + lockfile, `ruff` + `mypy --strict`, `pytest`, coverage ≥ 90 % on `src/`.
- License Apache-2.0. Public repo `github.com/thanatchon36/<name>` (create with `gh` if authenticated; otherwise `NEEDS_HUMAN.md`).
- Package name = repo name = CLI name = `<name>`.
- PyPI: prepare trusted-publishing workflow on tag; **do not** publish — the human releases.
- The paper's numbers come only from scripts in this repo. No hand-typed results. Ever.

---

## 1. Mission and thesis

**Problem.** Developers write rules in `CLAUDE.md` / `AGENTS.md` / `.cursorrules` and the agent still breaks them: redundant comments, verbal tics in comments and docs, Python one-liners where the rules said `jq`, edits outside the allowed paths, tests quietly "fixed" by embedding the expected answer. Today's remedy is to stack more probabilistic layers — longer rules, memory, more prompting — on top of a probabilistic component.

**Thesis.** Safety-critical systems solved this shape of problem decades ago: do not try to make the complex, unverifiable controller perfect; wrap it in a small, verified, *deterministic* monitor that has the authority to reject its actions (Simplex architecture, runtime assurance, interlocks). `<name>` is that monitor for coding agents. The LLM proposes a diff; `<name>` checks the diff against project rules with checks that are deterministic by construction; violations come back as agent-readable fix instructions; nothing in the enforcement path involves a model.

**One-line positioning.** *Rules for coding agents, enforced the way safety-critical systems enforce them: deterministic checks, severity levels, fail-closed defaults, independent verification, and an audit trail.*

**Why this survives vendor fixes.** Vendors will keep improving instruction-following. Project-specific policy still has to be enforced somewhere, and regulated teams (banks, healthcare, infrastructure) need *evidence* that it was — independent of how well-behaved the model is. The moat is methodology + evidence, not the checks.

**Contributions (software and paper, 50/50):**
1. A normative mapping from safety-critical engineering concepts to agent-rule enforcement (§3), argued and evaluated — not just asserted.
2. `<name>`: the tool (§4–5), with a determinism contract that is tested in CI.
3. A corpus study of real-world agent instruction files: what fraction of rules is deterministically checkable (§6.2).
4. A controlled evaluation of prompt-only vs. deterministic enforcement, with record-and-replay reproducibility (§6.3).
5. Dogfooding evidence: the tool enforced its own repository's rules on the agent that built it (§9, §10).

---

## 2. Evidence — verify before citing (fail-closed: unverifiable → not cited)

Leads supplied by the owner. Fetch each; keep only what you can confirm; record verified URLs + retrieval dates in `research/evidence.md`.
- `anthropics/claude-code` issue **#65961** (reported ~251 👍, open): reporter states one should not need rules + memory + hooks stacked to get clean code.
- `anthropics/claude-code` issue **#53454** (~181 reactions).
- `anthropics/claude-code` issue **#77136** (closed as fixed) — evidence of the vendor-fix risk; use it as such.
- Hacker News: a "skill" that stops agents from embedding answers (~542 points). Find the post; cite the HN thread and the linked repo.
- Competitors found at briefing time — study them, position against them honestly in `research/related-work.md` and in the paper:
  - `interlocks` (PyPI): a deterministic Python quality loop (ruff/pyright/coverage/…) for local, hooks, CI and agent-authored PRs. Overlap: determinism + agent PRs. Difference: it gates *generic code quality*; `<name>` compiles *project-specific natural-language rules* into checks and adds severity, deviations, self-protection and audit.
  - `veto` family (PyPI `veto`, `useveto`, `veto-cli`): policy runtime for agent *tool calls* / payments. Overlap: deterministic policy, default-deny, audit. Difference: tool-call authorization vs. *diff-level* rule enforcement derived from instruction files.
  - Also search for: `.cursorrules` / `AGENTS.md` linters, "agent rules" validators, semgrep-for-agents, OPA/Rego used with coding agents, Anthropic hooks examples, OpenCode plugins, Gemini CLI hooks, Codex hooks (if any). Record what exists and its adoption (stars, releases).

---

## 3. Design principles borrowed from safety-critical systems (normative)

Each row is a requirement, not an analogy. The paper argues the mapping; the code implements it; tests prove it.

| # | Safety-critical concept | Requirement in `<name>` | Phase |
|---|---|---|---|
| P1 | Simplex / runtime assurance (verified monitor wraps unverified controller) | Agent proposes a diff; `<name>` accepts/rejects; the monitor is never inside the generation loop; no model in the enforcement path | MVP |
| P2 | Independence of verification (DO-178C, IEC 61508) | The agent cannot modify its monitor: diffs touching the rule set, lockfile, hook configs, CI, or `<name>` itself are **critical** violations unless a human approval exists (§4.6) | MVP |
| P3 | MISRA decidability classes | Every rule declares `decidability: deterministic | heuristic | undecidable`. Only the deterministic tier may block. Heuristic warns. Undecidable is never evaluated by `<name>`; it is routed to humans/LLM-judges *outside* the tool and marked as such | MVP |
| P4 | SIL / ASIL / DAL | `severity: advisory | required | critical` → warn / block / block + human sign-off | MVP |
| P5 | Fail-safe, fail-closed, bounded execution (WCET) | Per-check timeouts and total budget; on engine crash or timeout: required/critical rules **fail-closed** (block), advisory fail-open; regex engines run with size caps and step limits (no ReDoS hang) | MVP |
| P6 | Tool qualification (DO-330) | A rule without ≥1 passing and ≥1 failing fixture is invalid and cannot load. `<name> test-rules` runs all fixtures; CI runs them; editing a rule = regression run | MVP |
| P7 | Alarm management (prioritisation, flood avoidance) | Report orders by severity, dedupes, caps advisory noise, gives exactly one imperative *Fix:* line per violation, bounded total length so the agent's context is not flooded | MVP |
| P8 | MISRA deviation procedure | Inline deviations with reason + approver + optional expiry; agent-authored deviations are valid only for advisory rules; approvers live in a protected file | v2 |
| P9 | Requirements traceability | Rule IDs; each rule records the instruction-file line it came from; every run appends to an append-only audit log keyed by diff hash + rule-set hash | v2 |
| P10 | Near-miss reporting / safety culture | `<name> stats`: violations per rule, self-correction cycles, rules that never fire (review candidates) | v2 |
| P11 | STPA / HAZOP | A guided procedure (docs + template) to derive rules from losses → hazards → unsafe actions → constraints; guide words to stress-test rules | v3 (docs only) |
| P12 | Assurance case (GSN) | `<name> report --framework` emits an evidence summary mappable to NIST AI RMF / ISO 42001 / EU AI Act Art. 9 / MAS AI risk guidance | v3 |

**What we deliberately do not import:** certification bureaucracy, formal verification of natural-language rules, and "safety-critical" branding for the free tier. The *concepts* carry the value; the paperwork would kill adoption.

---

## 4. Product specification

### 4.1 CLI surface
```
<name> init            # detect CLAUDE.md/AGENTS.md/.cursorrules, scaffold rules from templates, install hooks, write lockfile
<name> compile         # instruction file → rule proposals + report of lines that cannot be compiled (and why)
<name> check           # run rules on a diff (staged | working tree vs baseline | --diff FILE); JSON + text report; exit code
<name> test-rules      # run every rule's fixtures (tool qualification)
<name> lock            # write rules.lock (sha256 of the rule set); human action — agents are blocked from running it
<name> hook <harness>  # adapter entrypoints: claude-code | pre-commit | git | opencode | codex | gemini
<name> report          # audit log → markdown/JSON; --framework nist-ai-rmf|iso-42001|eu-ai-act|mas (v3)
<name> stats           # near-miss and self-correction metrics
<name> doctor          # verify installation, hook wiring, lock integrity, determinism self-test
```

### 4.2 Rule schema (YAML; `src/<name>/engine/schema.py` is the source of truth)
```yaml
version: 1
rules:
  - id: R-012                         # stable, never reused
    title: Use jq, not Python, for JSON in shell scripts
    source: CLAUDE.md:L14             # traceability (P9)
    severity: required                # advisory | required | critical  (P4)
    decidability: deterministic       # deterministic | heuristic | undecidable  (P3)
    scope: diff                       # diff | file | repo
    applies_to: ["**/*.sh", "**/*.bash"]
    check:
      engine: regex                   # regex | glob | ast | jq | shell | python
      pattern: 'python3?\s+-c\s+.*\bjson\b'
      on: added_lines                 # added_lines | hunks | file
    message: "Replace the Python one-liner with jq. Example: jq -r '.key' file.json"
    fixtures:                         # P6 — both lists non-empty or the rule will not load
      fail: ["python3 -c 'import json,sys; print(json.load(sys.stdin)[\"k\"])' < f.json"]
      pass: ["jq -r '.k' f.json"]
    deviations: allowed               # allowed | forbidden
    tags: [shell, tooling]
```
Engines in MVP: `regex` (bounded), `glob` (path policy), `ast` (Python, via `ast`), `jq` (optional, subprocess with timeout, `jq` on PATH), `shell` (opt-in only, sandboxed: temp dir, no network, timeout, allowlisted binaries), `python` (user plugin; treated as protected code under P2). Multi-language AST (tree-sitter) is **Won't** for v1.

### 4.3 Enforcement semantics
- Core exit codes: `0` pass or advisory-only · `1` required/critical violations · `3` engine error. Adapters map these to harness semantics and apply the P5 fail policy.
- `check` operates on **hunks of the diff** by default (`added_lines` / `hunks`); `file` and `repo` scopes exist for rules that need them (e.g. "no new dependencies" diffs the lockfile; "tests are read-only in this task" is path policy).
- Baseline for "diff": the session start commit (recorded by the harness adapter) or `HEAD`; configurable.
- A rule-set hash mismatch against `rules.lock` → fail-closed for everything until a human runs `<name> lock` (P2).

### 4.4 Alarm management (P7) — the report format is part of the product
```
BLOCKED — 1 critical, 2 required, 7 advisory (showing 5)
[R-001 critical] Agent edited protected path .claude/settings.json — Fix: revert this change; a human must apply it.
[R-012 required] src/tools/sync.sh:41 uses python -c for JSON — Fix: replace with jq -r '.key' file.json
...
+2 advisory not shown — run `<name> report`
```
Rules: severity-first; stable ordering (path, line, id); dedupe identical findings; cap advisory at 5; hard cap ~2,000 characters for hook messages (configurable); exactly one `Fix:` per finding; machine-readable JSON alongside.

### 4.5 Harness adapters (thin; the core is harness-agnostic: stdin diff → stdout report → exit code)
- **Claude Code** (primary): `PreToolUse` on `Bash` to block `--no-verify`, force-push, history rewrites, `rm -rf` outside the repo, and shell edits of protected paths; `PostToolUse` on `Edit|Write|MultiEdit` to check the produced diff and return a blocking decision with the alarm-managed message; `Stop` to run the full check and refuse to stop while required/critical findings remain; `SessionStart` to record the baseline. **Verify the current hook API in the official docs at build time** (event names, stdin JSON, exit-code and JSON-decision semantics change between releases). Put the exact contract you verified, with the doc URL and date, in `research/harness-apis.md`.
- **pre-commit** and plain **git hooks** (pre-commit, pre-push): the universal fallback that works with any agent.
- **CI** (`GitHub Actions` example): the final gate.
- **OpenCode plugin**: Should. **Codex / Gemini CLI**: Could — only if they expose a hook mechanism you verified; otherwise document the git-hook path for them.
- Defense in depth is intentional: tool-call hook (immediate) → git hook (universal) → CI (final).

### 4.6 Self-protection (P2)
Protected set (default, extensible): `rules/`, `rules.lock`, `.<name>/`, `.claude/settings*.json`, `.pre-commit-config.yaml`, `.github/workflows/`, `.opencode/`, `.codex/`, `.gemini/`, and the package's own source when installed in editable mode. Any agent diff touching these → critical finding. Threat model (state it in the paper): the agent is *untrusted but mediated* — every write and shell command passes through the harness hook. Bypasses that require a misconfigured harness are out of scope and listed as limitations.

### 4.7 Deviations (P8, v2)
`# <name>: deviate R-012 reason="vendor script, no jq on target" approved-by="@handle" expires=2026-12-31`
Valid only if the approver is listed in the protected `.<name>/approvers` file; an agent-introduced deviation of a required/critical rule is itself a critical finding; expired deviations count as violations; all deviations are logged.

### 4.8 Audit (P9, v2)
`.<name>/audit.jsonl`, append-only: timestamp (the only non-deterministic field), harness, session id, diff hash, rule-set hash, per-rule outcome, exit code, elapsed ms. `<name> report` renders it. `<name> stats` derives P10 metrics.

### 4.9 `compile` — honest conversion of natural language to checks
Deterministic conversion of arbitrary prose is impossible, so `compile` is: (a) a template library of common rule shapes (§4.10) matched to instruction-file lines by deterministic patterns, and (b) a report of every line that could not be compiled, labelled `heuristic-candidate` or `undecidable`, so the human sees exactly what is *not* enforced. Optional `--assist` may use an LLM **at authoring time only** to propose rules; a proposal is accepted only if its own fixtures pass. Runtime enforcement never calls a model.

### 4.10 Starter packs (`rules/packs/*.yaml`, each rule with fixtures)
- `hygiene-python`: no bare `except`, no `print` in library code, no TODO without reference, docstring length cap, comment-density ratio (heuristic), no comments that restate the line (heuristic).
- `voice`: banned phrases/verbal tics in comments, docstrings, commit messages and markdown (configurable list; ship a default).
- `shell-tooling`: `jq` for JSON in shell, no `curl | sh`, no `sudo` in scripts.
- `scope`: allowed-path policy, no new dependencies, no deleted tests, no `--no-verify`, no force-push, no history rewrite.
- `no-answer-embedding`: tests are read-only in the task (deterministic, path policy); literal-lookup patterns that hard-code expected outputs (heuristic). This is the HN pain point — cite it.
- `secrets`: common key/token patterns (deterministic).
- `protected-set`: the P2 rules themselves.

---

## 5. Determinism contract (tested, not promised)
- Same inputs (diff, rule set, config) → byte-identical report JSON (`sort_keys`, stable ordering, no timestamps outside the audit log, UTF-8 everywhere, locale/TZ-independent).
- No network, no model, no randomness in `check`.
- Bounded runtime: per-check timeout, total budget, input size caps; regex via a bounded engine or explicit size/step limits.
- Tests: run the engine twice in separate processes and compare hashes; CI matrix linux + macOS; a mutation-style test that corrupts a rule file and asserts fail-closed; adversarial tests for ReDoS-shaped patterns and oversized inputs.
- `<name> doctor` runs a determinism self-test on install.

---

## 6. Research program

### 6.1 Research questions
- **RQ1 (corpus).** What fraction of rules in real-world agent instruction files is deterministically checkable, heuristic, or undecidable, and what rule categories dominate?
- **RQ2 (effectiveness).** Compared with rules in the instruction file alone, does deterministic hook enforcement reduce rule violations in the final diff, and at what cost in turns, tokens and wall-clock?
- **RQ3 (safety properties).** Does the tool hold its determinism and fail-closed guarantees under adversarial inputs (ReDoS patterns, oversized diffs, corrupted rules, timeouts)? What is the latency distribution per check?
- **RQ4 (alarm management).** Does severity-first, capped reporting improve self-correction (fewer rejection cycles to a clean diff) versus a flat, unprioritised list?
- **RQ5 (independence, Could).** When prompted adversarially to "make the checks pass", how often does the agent attempt to edit rules/hooks or add deviations, and are all attempts blocked?

Pre-register the analysis in `bench/ANALYSIS_PLAN.md` **before** running RQ2–RQ5: metrics, comparisons, tests, exclusion rules. Do not change it afterwards; if you must, log the change and the reason.

### 6.2 Corpus study (RQ1)
- Collect up to `CORPUS_MAX_FILES` public `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `GEMINI.md`, `.windsurfrules` via GitHub code search (`gh api`; stratify by file type). Record repo, path, commit SHA, license.
- Extract rule-like lines (imperatives, "always/never/do not/prefer/use"). Label each line: category (style, tooling, scope, process, testing, security, voice, other) and decidability (P3).
- Labelling: deterministic rubric first; model-assisted labelling only with a fixed prompt, temperature 0, two independent passes, agreement (Cohen's κ) reported, all labels published for audit. State clearly in the paper that labels are model-assisted.
- Licensing (fail-closed): store verbatim lines only from OSI-licensed repos; otherwise store hash + labels only. Never store anything that looks like a secret or personal data.
- Output: `corpus/data/labels.parquet` (+ CSV), `corpus/README.md` with the exact query and date, and figures for the paper.

### 6.3 Benchmark (RQ2, RQ4, RQ5)
- **Tasks:** 20–30 small, self-contained coding tasks in `bench/tasks/<id>/` (a mini repo, `TASK.md`, hidden tests, a task-specific rule set of 5–10 rules mixing severities and decidability tiers, with fixtures). Mix languages: Python and shell at minimum.
- **Agent under test:** Claude Code headless (`claude -p … --output-format json`, max-turns capped, the cheapest capable model available). A second harness (OpenCode with a local model) is Could.
- **Conditions:** A — no rules; B — rules in `CLAUDE.md` only; C — B + `<name>` hooks with alarm management; D — C with flat, unprioritised reports (ablation for RQ4); E — C with an adversarial task prompt (RQ5, Could).
- **Metrics:** final-diff violations per rule (ground truth = the deterministic engine, identical for all conditions — acknowledge the circularity for deterministic rules and focus the comparison on B vs A, on rejection cycles and overhead in C, and on heuristic-tier compliance); hidden-test pass rate (task success must not degrade); turns, tokens, wall-clock; rejection count; blocked circumvention attempts.
- **Design:** ≥3 repeats per task×condition when the run budget allows; otherwise fewer with n stated per cell. Paired, non-parametric comparisons (e.g. Wilcoxon signed-rank on per-task means) with bootstrap CIs; no p-hacking — the plan is pre-registered.
- **Record and replay (non-negotiable):** every run's transcript, final diff and metrics are recorded (secrets scrubbed) under `bench/recorded/`. `bench/replay.py` recomputes every number in the paper from recordings with **no API key**. CI runs replay. This is how readers reproduce the paper for free.
- **Budget:** `BENCH_MAX_RUNS`. Order runs so that partial budgets still yield a complete B-vs-C comparison on a subset of tasks before adding repeats or conditions.

### 6.4 Safety-property tests (RQ3)
A test suite, not an experiment: adversarial regexes, 50 MB diffs, corrupted YAML, lockfile mismatch, timeouts injected into engines, agent-authored deviations, protected-path edits. Report pass/fail tables and latency percentiles from `pytest --benchmark` or equivalent.

---

## 7. Paper specification (`paper/`)
- **Title (working):** *`<name>`: Deterministic Runtime Assurance for AI Coding Agents — Borrowing Safety-Critical Systems Engineering to Enforce Agent Instruction Files.*
- **Form:** arXiv-style, cs.SE, 8–12 pages + appendix. LaTeX (`main.tex`, build via `latexmk`); if TeX is unavailable, Markdown + pandoc with the same content. `make paper` regenerates figures, tables and the PDF from `bench/results/`, `corpus/data/` and test reports. Generated files are never hand-edited.
- **Structure:** Abstract · 1 Introduction (pain, evidence from §2, thesis, contributions) · 2 Background (instruction files and harness hooks; the safety-critical concepts P1–P12) · 3 Design (mapping table as the spine; schema; semantics; self-protection; audit; what is not imported) · 4 Corpus study (RQ1) · 5 Evaluation (RQ2–RQ5; setup; results; each RQ answered explicitly) · 6 Discussion (undecidable rules, agent gaming, overhead, the assurance positioning and governance mapping P12, dogfooding evidence) · 7 Related work (MISRA, DO-178C/DO-330, IEC 61508, Simplex/runtime verification, policy-as-code: OPA, semgrep, pre-commit, linters; agent guardrails: NeMo Guardrails, Guardrails AI, veto, interlocks, Anthropic hooks, Cursor rules; instruction-following and reward-hacking/answer-embedding literature) · 8 Threats to validity · 9 Conclusion and future work · Appendix: schema spec, full results, reproducibility checklist, the tool's own audit log from building this repo.
- **Rules:** every claim in the abstract maps to an RQ result; every number has a generating script; limitations are stated before conclusions; competitors are described accurately and generously.
- **Citation integrity (fail-closed):** every bib entry must be resolved at build time (DOI or URL fetched; title matched) and recorded in `paper/refs_verified.json`. Unresolvable → removed from the bib and from the text. No invented references, no invented quotes.
- **Reproducibility:** `README.md` in `paper/` with one command to rebuild; artifact availability statement; the replay path requires no API key.
- **Owner excluded by default from any identifying data; no employer names in headline results.**

---

## 8. Engineering standards
- `src/` layout, typed public API, `py.typed`. `ruff` (format + lint), `mypy --strict`, `pytest` with `-p no:randomly`-equivalent determinism, coverage ≥ 90 % on `src/`.
- `uv.lock` committed; dependencies pinned; minimal runtime deps (`pyyaml`, `click`/`typer`, `rich` optional). No network at runtime.
- CI: lint, types, tests, fixtures, determinism test, replay, paper build (PDF as artifact), on linux + macOS.
- `make check` = lint + types + tests + `test-rules` + determinism self-test + `<name> check` on the repo's own working tree.
- Docs: `README.md` (quick start in ≤ 10 lines, one GIF or terminal cast of a blocked edit and the agent self-correcting), `docs/` (concepts P1–P12, schema reference, adapters, writing rules, STPA guide v3), `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`.
- Conventional Commits; small commits; never force-push, never rewrite history, never `--no-verify`.
- Optional, non-blocking integration points: reuse the instruction-file parsing ideas from `thanatchon36/upfront`; make `<name> report --framework` output consumable by `thanatchon36/airmkit`. Keep `<name>` independent of both.

---

## 9. Operating constraints for the agent building this (the same principles, applied to you)
1. **Containment.** Write only inside the project directory. Network only to package registries, GitHub, official docs, arXiv/ACM/IEEE/DOI resolvers for references, and GitHub search for the corpus.
2. **Fail-closed.** Unsure about a license → exclude. Unresolvable reference → drop. Possible secret → never commit. Destructive or irreversible → `NEEDS_HUMAN.md`.
3. **Independence.** Phase 7 verification is done by a fresh subagent that has not seen the implementation. From Phase 2 onward, `<name>` runs as a hook on this very repository and enforces Appendix A on you; its audit log is a paper appendix.
4. **Bounded.** Respect §0.2. Cut by MoSCoW (§10.1). Never cut tests, fixtures, determinism checks or the replay path.
5. **Traceable.** `DECISIONS.md`, `STATUS.md`, audit log, one commit per checkpoint.
6. **Reversible-first.** Prefer actions that can be undone. Branches over history edits. Copies over in-place rewrites of recorded data.
7. **No fabrication.** Never invent results, fixtures that trivially pass, references, or competitor claims. An experiment that did not run is reported as not run, with the reason.
8. **Deterministic builds.** Pinned dependencies; the same commands produce the same artifacts on a clean clone.

---

## 10. Phases and checkpoints

### 10.1 MoSCoW (cut from the bottom when a budget bites)
- **Must:** engine + schema + fixtures + determinism tests; Claude Code hook; pre-commit/git hooks; alarm management; self-protection; starter packs; `compile` (templates + uncompilable report); corpus study (RQ1, reduced n acceptable); benchmark B vs C on ≥10 tasks (RQ2); paper with real numbers; README; CI.
- **Should:** audit log + `report` + `stats`; deviations; OpenCode plugin; RQ3 full suite; RQ4 ablation; ≥3 repeats.
- **Could:** Codex/Gemini adapters; RQ5 adversarial; `report --framework`; STPA guide; terminal cast.
- **Won't (v1):** LLM-judge at runtime; hosted service; multi-language AST; a UI.

### 10.2 Phases
- **Phase 0 — Setup (≤ 1 h).** Pick the name (Appendix C). `git init`, LICENSE, `pyproject.toml`, `uv` env, CI skeleton, `make check` stub, `STATUS.md`, `DECISIONS.md`, `NEEDS_HUMAN.md`, `research/`, `paper/` skeleton with RQs and empty result sections. Write Appendix A as the repo's `CLAUDE.md` and `AGENTS.md`. Create the GitHub repo if `gh` is authenticated. Commit.
- **Phase 1 — Research sprint (≤ 3 h).** Verify §2 evidence; survey competitors; verify harness hook APIs (`research/harness-apis.md` with URLs + dates); write `research/related-work.md` with verified references only; draft `bench/ANALYSIS_PLAN.md` and `corpus/README.md` query plan; fill the paper's Background and Related-work skeletons. Commit.
- **Phase 2 — Core engine (≤ 6 h).** Schema, loader, lockfile, engines, runner, report (alarm management), exit codes, fixtures runner, determinism tests, adversarial tests. **As soon as `check` works, install `<name>` as this repo's Claude Code hook and pre-commit hook and keep it on for the rest of the mission.** Starter packs with fixtures. Commit.
- **Phase 3 — Adapters (≤ 3 h).** Claude Code (all four events), pre-commit, git hooks, CI example; OpenCode if Should budget remains. Integration tests that simulate each harness's stdin/stdout contract. `doctor`. Commit.
- **Phase 4 — Corpus study (≤ 3 h).** Collect, extract, label, analyse, figures. Fill the paper's §4. Commit.
- **Phase 5 — Benchmark (≤ 8 h).** Build tasks and rule sets with fixtures; harness runner; run B vs C first on ≥10 tasks, then A, then repeats, then D/E as budget allows; record everything; `replay.py`; results tables and figures via scripts. Fill the paper's §5. Commit.
- **Phase 6 — Paper (≤ 6 h).** Complete all sections; citation-integrity build; threats to validity; appendix with the repo's own audit log; `make paper` green; proofread for claims without evidence. Commit.
- **Phase 7 — Hardening and release prep (≤ 3 h).** Docs, README demo, CHANGELOG, trusted-publishing workflow (unpublished), security review of the sandboxed engines. Then independent verification: spawn a fresh subagent with the instruction *"From a clean clone, run `make check`, `make paper` and `bench/replay.py`; then try to make a required rule pass without satisfying it — edit rules, disable hooks, add deviations, use `--no-verify`. Report every success as a defect."* Fix defects, re-verify, write `FINAL_REPORT.md` (what shipped, what was cut and why, budget used, NEEDS_HUMAN items). Final commit and push.

Each phase: `make check` green → `STATUS.md` → commit. If a budget is exhausted mid-phase, finish the current checkpoint, cut per §10.1, record the cut, continue.

---

## 11. Definition of Done
- [ ] `make check` green on a clean clone (linux and macOS in CI).
- [ ] Determinism test, fail-closed tests and fixture suite pass; every shipped rule has fixtures.
- [ ] Claude Code hook demonstrably blocks a required violation and the agent self-corrects (recorded in README).
- [ ] pre-commit/git hook path works with no harness.
- [ ] Corpus study results with stated n and labelling method.
- [ ] Benchmark B vs C on ≥10 tasks with recordings and a working `replay.py` that needs no API key.
- [ ] Paper builds from scripts; every number traceable; every reference verified; limitations stated; competitors described fairly.
- [ ] The repo's own audit log shows `<name>` enforcing Appendix A during development.
- [ ] Independent verification subagent found no unfixed bypass.
- [ ] `FINAL_REPORT.md`, `NEEDS_HUMAN.md`, `CHANGELOG.md` written; everything committed and pushed; PyPI left to the human.

---

## 12. Target repository layout
```
<name>/
  MISSION.md  README.md  LICENSE  CLAUDE.md  AGENTS.md  CHANGELOG.md  CONTRIBUTING.md  SECURITY.md
  STATUS.md  DECISIONS.md  NEEDS_HUMAN.md  FINAL_REPORT.md  Makefile  pyproject.toml  uv.lock
  rules/            # this repo's own rules + rules.lock
  rules/packs/      # starter packs with fixtures
  src/<name>/
    cli.py
    engine/   schema.py loader.py lock.py runner.py report.py audit.py checks/{regex,glob,ast,jq,shell,python}.py
    adapters/ claude_code.py precommit.py git_hook.py ci.py opencode/ codex.py gemini.py
    compile/  templates/ compiler.py
  tests/            # unit, determinism, adversarial, adapters, fixtures
  bench/            # tasks/ rulesets/ harness/ recorded/ results/ replay.py ANALYSIS_PLAN.md
  corpus/           # collect.py extract.py label.py analyse.py data/ README.md
  paper/            # main.tex figures/ tables/ refs.bib refs_verified.json build.sh README.md
  research/         # evidence.md related-work.md harness-apis.md
  docs/
  .github/workflows/ci.yml  .pre-commit-config.yaml  .claude/settings.json  .<name>/
```

---

## Appendix A — This repository's own `CLAUDE.md` (enforced by `<name>` from Phase 2; also written as `AGENTS.md`)
```
# Rules for agents working in this repository
Scope
- Edit only inside this repository. Never touch rules/, rules.lock, .claude/, .pre-commit-config.yaml,
  .github/workflows/ or .<name>/ — a human changes those.
- Never run git with --no-verify, --force, or history-rewriting commands. Never rm -rf outside the repo.
- Do not add runtime dependencies without recording the reason in DECISIONS.md.
Code
- Python ≥ 3.11, ruff-formatted, mypy --strict clean. No bare except. No print() in src/ (use logging).
- No comments that restate the code. Docstrings ≤ 8 lines. No TODO without an issue reference.
- Use jq for JSON in shell scripts; no python -c one-liners in *.sh.
Tests and evidence
- Never modify a test to make it pass; never hard-code expected outputs; never fabricate fixtures, results or references.
- Every rule you add ships with at least one passing and one failing fixture.
Voice
- No filler phrases in comments, docs or commit messages (configured list in rules/packs/voice.yaml).
Process
- Commit at every checkpoint with Conventional Commits. Keep STATUS.md and DECISIONS.md current.
```

## Appendix B — A heuristic-tier rule, for contrast with §4.2
```yaml
  - id: R-031
    title: Comment restates the code on the next line
    source: CLAUDE.md:L9
    severity: advisory
    decidability: heuristic            # token-overlap heuristic; warns only, never blocks
    scope: diff
    applies_to: ["**/*.py"]
    check:
      engine: python
      plugin: packs.hygiene.restating_comment   # overlap ≥ 0.8 between comment tokens and next code line tokens
    message: "Delete the comment or make it say why, not what."
    fixtures:
      fail: ["# increment counter\ncounter += 1"]
      pass: ["# compensate for the off-by-one in the vendor API\ncounter += 1"]
    deviations: allowed
```

## Appendix C — Name selection (Phase 0, deterministic procedure)
Candidates in priority order: `abide`, `hardstop`, `failclosed`, `diffgate`, `lockout`, `rulebag`.
For each, in order: (1) `https://pypi.org/pypi/<candidate>/json` must return 404; (2) no GitHub repository with that name in the agent/devtools space with > 100 stars; (3) no well-known product of that name in the AI-agent policy space (web search). Pick the first candidate passing all three. Already excluded: `interlock*` (occupied by `interlocks`, `interlock-cb`, `interlock-control-plane`) and `veto*` (occupied by the `veto` policy-runtime family). If all six fail, generate three more two-syllable, safety-flavoured names and repeat. Record the evidence in `DECISIONS.md`. Then replace `<name>` everywhere except in this file.
