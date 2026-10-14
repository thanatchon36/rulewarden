# Related work (verified references only)

Every bracketed key resolves in `paper/refs_verified.json` (DOI via Crossref, arXiv export API, or URL fetched and
title-matched, 2026-10-14). Star counts and release counts were fetched on 2026-10-14 via `gh api` / PyPI JSON and will drift.

## 1. Closest tools (coding-agent policy enforcement)

| Tool | What it is (from its own docs) | Adoption | Overlap with rulewarden | Difference |
|---|---|---|---|---|
| **Cupcake** [cupcake] (eqtylab) | Policy enforcement layer for AI coding agents. Intercepts harness events through hooks and evaluates them against OPA/Rego policies compiled to Wasm. Also supports an LLM-as-judge "Watchdog". Decisions: allow / modify / block / warn / require-review. Claude Code, Cursor, Factory AI and OpenCode are supported. Says it turns rules in `CLAUDE.md` / `AGENT.md` / `.cursor/rules` into enforceable policies. Audit trails. | 297★, Apache-2.0, open-sourced 2025-12-10 | Very high: deterministic policy, hooks, block-with-feedback, audit, multi-harness. | Cupcake is a general **tool-call** policy engine (Rego, with optional LLM judge on the enforcement path). rulewarden is narrower. It checks the **diff**, keeps a model out of the enforcement path entirely (P1), makes a rule without passing and failing fixtures unloadable (P6), assigns every rule a decidability tier where only deterministic rules may block (P3), locks the rule set fail-closed (P2/P5), and caps the report to fit the agent's context (P7). Cupcake has a larger harness surface and far more expressive policies. |
| **AgentLint** [agentlint] (mauhpr; PyPI `agentlint`) | Checks proposed file writes, edits and shell commands. Blocks risky patterns and returns actionable feedback. 77 rules in 8 packs, three levels (ERROR blocks, WARNING advises, INFO reports). Approvals, time-limited exceptions, `agentlint ci --diff`. Claude Code, Codex, Cursor, Gemini CLI and more. | 38★, 62 PyPI releases, MIT | Very high: severity levels, packs, CI mode, approvals, test-weakening and CI-edit detection. | AgentLint ships a fixed catalogue of general guardrails. rulewarden **compiles project-specific instruction-file lines** into rules with provenance (`source: CLAUDE.md:L14`), reports which lines could *not* be compiled, requires fixtures per rule, and adds a lockfile and decidability tiers. |
| **agent-rules** [agentrules0x] (0xelitesystem) | Extracts imperative rules from `CLAUDE.md` / `AGENTS.md` / `.cursorrules` and audits a **session transcript** after the fact. High-confidence built-in matchers plus a low-confidence keyword fallback. Compliance score A–F. | 0★, MIT, git install only | Rule extraction from instruction files; honesty about confidence tiers. | Post-hoc transcript audit, not runtime enforcement on the diff. No blocking during a session. |
| **interlocks** [interlocks] (PyPI `interlocks`) | One deterministic Python quality loop (Ruff, basedpyright, coverage, mutmut, deptry, import-linter, pip-audit, …) for local edits, git hooks, CI and agent-authored PRs. | 4★, 10 releases, MIT | Determinism; same gate for humans and agents. | Gates **generic code quality** via existing tools. rulewarden compiles **project-specific natural-language rules** and adds severity, deviations, self-protection and audit. |
| **veto** family [vetopypi] (PyPI `veto`, `useveto`, `veto-cli`) | `veto`: policy runtime that wraps an agent's tools and evaluates deterministic policy before each handler runs. `veto-cli`: agent-payment authorization with signed decision receipts. | `veto` 18 releases. `useveto/python` 2★. `veto-cli` 1★ | Deterministic policy, default-deny, audit/receipts. | Authorizes **tool calls / payments** inside an agent application. rulewarden enforces **diff-level** rules derived from instruction files at the harness/git/CI boundary. |
| **CC Safety Net** [ccsafetynet] | Pre-execution guard. Blocks destructive git/filesystem commands (also inside `bash -c` / `python -c`) and secret access. 16 coding CLIs. | 1,619★ | PreToolUse command blocking; force-push / `rm -rf` rules. | Fixed command-safety policy. No project rules, no diff checks. |
| **Hardstop** [hardstop] | Validates every shell command against 428 patterns, fail-closed, plus optional LLM analysis for edge cases. | 32★ | Fail-closed shell-command gate for Claude Code. | Commands only. An LLM is on the decision path for edge cases. |
| **diffgate** [diffgate] | Reads a unified diff and reports changes that pass CI but should fail review (newly skipped tests, swallowed exceptions, disabled TLS verification, removed auth decorators). | 0★, 1 release | Diff-level, deterministic, agent-adjacent. | Fixed catalogue. No instruction-file compilation, harness integration or lockfile. |
| **FailproofAI** [failproofai] | Observability and enforcement across 12 agent harnesses. 40 built-in policies, dashboard. | 5,267★ | Hook-based blocking across harnesses. | Platform with daemon and dashboard. No rule compilation or decidability tiers. |
| **Open Bias** [openbias] | Policy-enforcement **proxy** between app and LLM provider. Enforces `RULES.md`, with evaluators that can be LLM-based. | 144★, Apache-2.0 | Rules-from-markdown enforcement. | Sits on the model API path and can use models to judge. rulewarden sits on the action/diff path and is model-free. |
| **Microsoft Agent Governance Toolkit** [msagt] | Policy enforcement, identity, sandboxing and tamper-evident audit for autonomous agents. Intercepts tool calls in deterministic code. | 6,425★ | Deterministic interception, audit for regulators. | General agent governance. Not specific to coding-agent instruction files or diffs. |
| **agnix** [agnix] | Linter/LSP for agent configs (`CLAUDE.md`, `SKILL.md`, hooks, MCP). 455 rules. | 450★ | Reads instruction files. | Validates the **config files themselves**, not whether the agent's output obeys them. |
| **Ruler** [ruler], rulesync | Distribute one rule source to many agents' config formats. | 2,945★ / 1,514★ | Same input files. | Distribution, not enforcement. |

**Honest positioning.** The tool surface is crowded: hook-based blocking, severity levels, packs, approvals and audit
already exist (Cupcake, AgentLint, FailproofAI). rulewarden's claim is **not** novel checks. It is (a) an explicit
**safety-critical methodology** (decidability tiers, fixtures-as-tool-qualification, lockfile-backed fail-closed
semantics, alarm management, independence of the monitor) implemented and *tested* as properties, (b) honest
**compilation** of instruction files with an explicit report of what is *not* enforced, and (c) **evidence**: a
corpus study and a replayable controlled evaluation. A paper should say exactly this.

## 2. Empirical studies of agent instruction files (closest to RQ1/RQ2)

- **Yan 2026** [yan2026donot]: 481 `CLAUDE.md` files. Only ~4–16 % of retrieved *security* rules have a matching Claude Code
  built-in control (4.4 %, 95 % CI 2.6–6.7 % under the strictest standard). LLM-matched with two human annotators.
  Calls `CLAUDE.md` "a write-only channel". **Closest to RQ1.** We differ: all rule categories, the question is
  "checkable by a deterministic diff/command check" rather than "covered by a built-in control", and we ship the
  enforcement.
- **Zhang et al. 2026, "Guardrails Beat Guidance"** [zhang2026guardrails]: 679 rule files (25,532 rules), >5,000 Claude Code
  runs on SWE-bench Verified. Rules raise task success about as much whether random or curated (+13.8 pp). Individually
  beneficial rules are negative constraints. Relevant to RQ2: rules-in-context may act as priming rather than
  constraint, which motivates measuring *compliance* rather than only task success.
- **Khatri 2026** [khatri2026contextfiles]: controlled ablation, Claude Code and Codex, 17 tasks, 288 runs. Context-file
  strategy does not measurably change correctness. Methodologically closest to our §6.3 design (paired tasks, gold tests).
- **Chatlatanagulchai et al. 2025a** [chatlatanagulchai2025manifests] (253 `CLAUDE.md` files) and **2025b**
  [agentreadmes2025] (2,303 context files, 16 instruction types; security 14.8 %, performance 14.5 %): content
  taxonomies. We reuse the idea of a category taxonomy but label *decidability*, which they do not.
- **dos Santos et al. 2026** [dossantos2026smells]: six configuration smells in `AGENTS.md`/`CLAUDE.md` with automated
  heuristics (100 repos).
- **Chakrabarti 2026** [chakrabarti2026remembering]: instruction files grow without bound (+4.9 net instructions/commit).
  This supports the alarm-management argument: more rules in context ≠ more compliance.
- **Shi et al. 2026, Aletheia** [shi2026aletheia]: permission-minimality testing of rule files (security of the rules
  themselves). Complementary threat model.

## 3. Safety-critical and runtime-verification foundations

- Simplex architecture / runtime assurance: Seto et al. 1998 [seto1998simplex]; Sha 2001 [sha2001simplicity].
- Runtime verification: Leucker & Schallhart 2009 [leucker2009brief]. Runtime certification: Rushby 2008 [rushby2008runtime].
- Enforceable security policies / execution monitors (security automata): Schneider 2000 [schneider2000enforceable].
  This formally characterises which policies an execution monitor can enforce (safety properties). It is the
  theoretical counterpart of our decidability tiers.
- Standards: MISRA C:2023 [misra2023] (decidable/undecidable rule classification, deviation procedure); DO-178C [rtca_do178c]
  (independence; DO-330 tool qualification is a supplement to it); IEC 61508 [iec61508] (SIL); ISA-18.2 [isa182] (alarm
  management); GSN [gsnstandard]. STPA: Leveson 2011 [leveson2011engineering].
- Governance mappings: NIST AI RMF 1.0 [nist2023airmf]; ISO/IEC 42001 [iso42001]. EU AI Act: **dropped from the bib**
  (EUR-Lex not machine-resolvable from this environment; fail-closed). Mention without citation only if needed.

## 4. Policy-as-code and guardrails

OPA [opa], Semgrep [semgrep], pre-commit [precommit]; NeMo Guardrails [rebedea2023nemo]; Guardrails AI [guardrailsai].
These guard **LLM inputs/outputs** or **generic code**, not agent diffs against project instruction files.

## 5. Instruction following, reward hacking, test gaming

IFEval [zhou2023ifeval]; Concrete Problems in AI Safety [amodei2016concrete]; reward hacking [skalse2022defining];
ImpossibleBench [zhong2025impossiblebench]; SWE-bench [jimenez2023swebench]; SWE-agent [yang2024sweagent].

## 6. Methods

Cohen's κ [cohen1960kappa]; Wilcoxon signed-rank [wilcoxon1945]; bootstrap [efron1979bootstrap]; ReDoS [davis2018redos].

## 7. Harness documentation

Claude Code hooks [claudecodehooks]; Codex hooks [codexhooks]; Gemini CLI hooks [geminihooks]; AGENTS.md [agentsmd].
