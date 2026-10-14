---
title: "rulewarden: Deterministic Runtime Assurance for AI Coding Agents"
subtitle: "Borrowing Safety-Critical Systems Engineering to Enforce Agent Instruction Files"
---

# Abstract

*(Written last; every claim maps to an RQ result.)*

# 1 Introduction

# 2 Background

## 2.1 Agent instruction files and harness hooks

Coding agents read project-level instruction files (`CLAUDE.md`, `AGENTS.md` [@agentsmd], `.cursorrules`,
`GEMINI.md`) at session start and treat them as context. Empirical studies describe these files as growing,
configuration-like artifacts dominated by build/test commands, implementation notes and architecture
[@chatlatanagulchai2025manifests; @agentreadmes2025; @chakrabarti2026remembering]. Rules in such files are advisory:
the model interprets them, and nothing checks the result. Yan [@yan2026donot] calls `CLAUDE.md` a "write-only channel"
because a developer gets no feedback on whether any control enforces a written rule.

Harnesses now expose lifecycle **hooks**: external commands that receive a JSON description of an event (a tool call
about to run, a tool result, the agent trying to stop) and may veto it. Claude Code [@claudecodehooks], Codex
[@codexhooks] and Gemini CLI [@geminihooks] share the same shape: JSON on stdin, a decision on stdout or via exit code 2.
They differ in the details that decide safety. In Claude Code, for example, a hook that exits with code 1 or times out
is a *non-blocking* error, so a crashing policy hook fails open unless it is configured with `onFailure: "block"`.

## 2.2 Safety-critical concepts P1–P12

Safety-critical engineering faced a structurally similar problem: a complex controller that cannot be verified.
The **Simplex architecture** [@seto1998simplex; @sha2001simplicity] pairs an unverified high-performance controller
with a simple verified one and a decision module that switches to the safe controller when the envelope would be left.
Runtime verification [@leucker2009brief] and runtime certification [@rushby2008runtime] generalise this to monitors
that observe executions and check them against specifications. Schneider's execution monitors [@schneider2000enforceable]
characterise which policies a monitor can enforce at all: safety properties, decidable on finite prefixes. This is the
theoretical root of our decidability tiers. Standards contribute the rest of the vocabulary: MISRA's split between
decidable and undecidable rules and its deviation procedure [@misra2023]; independence of verification and tool
qualification in DO-178C [@rtca_do178c]; integrity levels in IEC 61508 [@iec61508]; alarm management in ISA-18.2
[@isa182]; hazard analysis via STPA [@leveson2011engineering]; and structured assurance arguments in GSN [@gsnstandard].
Section 3 turns each of these into a testable requirement (P1–P12).

# 3 Design

**Architecture.** rulewarden is a harness-agnostic core with thin adapters. The core takes a change (a unified
diff, a proposed file content, or a shell command), evaluates a locked rule set on it, and returns a report and an
exit code (0 pass or advisory only, 1 blocking findings, 3 engine error). Adapters translate harness events into
core calls: Claude Code (PreToolUse, PostToolUse, Stop, SessionStart), plain git hooks and the pre-commit
framework, CI, and pre-tool adapters for Codex, Gemini CLI and OpenCode. The layers form defence in depth. The agent
hook denies a tool call before it acts; the git hook works with any agent or none; CI is the final gate, which the
agent cannot reach. No model is called anywhere in the enforcement path.

**Threat model.** The agent is *untrusted but mediated*: every write and shell command passes through a harness
hook. The agent may make mistakes, cut corners under pressure, or try to make checks pass by editing the checks.
Bypasses that need a misconfigured harness, such as hooks that are not installed or a harness that ignores
`onFailure`, are out of scope and listed as limitations. Section 6 reports one such bypass that went through the
human operator instead.

**Requirements P1–P12.** Each safety-critical concept from §2.2 becomes a requirement with an implementation and a
test (Table 4).

| # | Concept | Requirement | Implementation and evidence |
|---|---|---|---|
| P1 | Simplex / runtime assurance | The agent proposes; a simple monitor accepts or rejects; no model in the enforcement path | PreToolUse evaluates the *proposed* content of Edit/Write before anything is written (`adapters/claude_code.py`); `tests/test_adapters.py` |
| P2 | Independence of verification | The agent cannot modify its monitor | `rules.lock` records SHA-256 of every rule file and protected path; a protected-path change is critical unless it matches the lock; only a human runs `lock`; command rules deny shell writes to protected paths (`engine/lock.py`, `protected-set` pack) |
| P3 | MISRA decidability | Every rule declares `deterministic`, `heuristic` or `undecidable`; only deterministic rules block | Schema rejects a blocking heuristic rule; undecidable rules carry no check and are listed, never evaluated (`engine/schema.py`) |
| P4 | Integrity levels | `advisory`, `required`, `critical` | Severity orders the report and sets blocking; critical marks independence violations |
| P5 | Fail-closed, bounded execution | Timeouts, budgets, ReDoS-safe regex; engine errors on blocking rules block | Static star-height screen for regexes, input caps, a forked watchdog with a wall-clock budget; harness `onFailure: block` (`engine/bounded.py`, `engine/regexsafe.py`) |
| P6 | Tool qualification | A rule without a passing and a failing fixture cannot load; the lock certifies qualification | `test-rules`; `lock` refuses to write unless every fixture passes (`engine/fixtures.py`) |
| P7 | Alarm management | Severity first, stable order, dedupe, advisory cap, one `Fix:` per finding, bounded length | `engine/report.py`; the flat reporter is the RQ4 ablation |
| P8 | Deviation procedure | Inline deviations with reason, approver, expiry; agent deviations of blocking rules are themselves critical | Approvers in a protected file; blocking-rule deviations valid only when registered by a human lock (`engine/deviations.py`) |
| P9 | Traceability | Rule ids, source line, hash-chained audit log keyed by diff and rule-set hash | `.rulewarden/audit.jsonl`, `report` verifies the chain (`engine/audit.py`) |
| P10 | Near-miss reporting | Violations per rule, self-correction cycles, rules that never fire | `rulewarden stats` |
| P11 | STPA | A guided procedure from losses to rules | Not implemented (v3, documentation only) |
| P12 | Assurance case | Evidence summary mapped to governance frameworks | `report --framework nist-ai-rmf` |

*Table 4. Requirements and their implementation.*

**Decidability of compliance.** Schneider's result [@schneider2000enforceable] says which properties a monitor can
enforce: safety properties that are decidable on finite prefixes. Our deterministic tier is the subset that is
decidable *on a single diff or command* with a bounded regex, glob, syntax-tree query or plugin. "No `print()` in
library code" qualifies; "write clean code" does not. A heuristic rule (for example "comments should not restate the
code") is approximated with known false positives, so it may only warn. This is the design decision that the corpus
study (§4) tests against what developers actually write.

**Determinism contract.** The same diff, rule set and configuration produce a byte-identical JSON report (sorted
keys, stable ordering, no timestamps outside the audit log, locale- and timezone-independent). `doctor` checks this
by running the engine in three processes with different `TZ`, locale and hash seeds and comparing report hashes.

# 4 Corpus study (RQ1)

**RQ1.** What fraction of rules in real-world agent instruction files is deterministically checkable, heuristic, or
undecidable, and what rule categories dominate?

**Method.** On {{corpus:collection.query_date}} we collected {{corpus:n_files|int}} instruction files through GitHub code
search, 60 per file type (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `GEMINI.md`, `.windsurfrules`), in API order.
We skipped forks, second files from an already sampled repository, files over 200 KB, and repositories without an
OSI-approved licence. This is a convenience sample, not a random one (`corpus/README.md`). The extractor that
`rulewarden compile` uses found {{corpus:n_lines|int}} rule-like lines (median {{corpus:lines_per_file_median|int}}
per file). Every line received two independent sets of labels. (1) A deterministic regex rubric (`corpus/label.py`)
assigns a category and a decidability tier relative to a checker that sees only the diff and the agent's commands.
(2) A model (Claude Haiku 5.5 through `claude -p`, no tools, fixed prompt `corpus/prompts/label_v1.txt`) labelled
every line twice in independent passes. It also says whether the line is a rule at all or merely describes the project.
All labels, raw model responses and scripts are published. The labels are rubric-based and model-assisted; no human
labelled the corpus.

**Reliability.** The two model passes agree substantially on decidability (Cohen's κ =
{{corpus:model.kappa_p1_p2_decidability|f2}}) and strongly on category (κ = {{corpus:model.kappa_p1_p2_category|f2}})
and on rule-versus-description (κ = {{corpus:model.kappa_p1_p2_is_rule|f2}}). The rubric and the model barely agree on
decidability (κ = {{corpus:model.kappa_rubric_p1_decidability|f2}}; raw agreement
{{corpus:model.rubric_model_agreement.share|pct}}). Table 2 shows where they diverge. Most lines the rubric calls
deterministic, because they name a concrete token, the model calls heuristic. An example is "Use `REAL*8` for all
floating-point variables", where a regex can flag violations but cannot confirm compliance everywhere. We therefore
report both labellings and treat their spread as the uncertainty of the estimate.

{{table:corpus_decidability}}

*Table 1. Decidability of {{corpus:n_lines|int}} rule-like lines (95% CIs from a bootstrap over files).*

{{table:corpus_confusion}}

*Table 2. Rubric (rows) against model pass 1 (columns).*

**Results.** Deterministically checkable rules are a minority under every labelling: the rubric
{{corpus:rubric_decidability.deterministic.share|pct}} ({{corpus:rubric_decidability.deterministic.ci95|ci}}),
the model {{corpus:model.decidability_p1.deterministic.share|pct}}
({{corpus:model.decidability_p1.deterministic.ci95|ci}}), and both together only
{{corpus:model.rubric_model_agreement.deterministic_by_both_share_of_all|pct}}. Restricting to lines the model calls
rules in both passes ({{corpus:model.rules_only.share_of_lines|pct}} of lines) barely changes this
(rubric {{corpus:model.rules_only.rubric.deterministic.share|pct}}, model
{{corpus:model.rules_only.model_p1.deterministic.share|pct}}). The rest splits differently by labeller: the rubric
calls most of it undecidable ({{corpus:rubric_decidability.undecidable.share|pct}}), while the model calls
{{corpus:model.decidability_p1.heuristic.share|pct}} heuristic and
{{corpus:model.decidability_p1.undecidable.share|pct}} undecidable. Per file, the median share of rubric-deterministic
lines is {{corpus:per_file_deterministic_share.median|pct}}, and {{corpus:per_file_deterministic_share.files_with_no_deterministic_rule|int}}
files contain none. The shipped `compile` templates match only {{corpus:compilable.share_all|pct}} of lines
({{corpus:compilable.n|int}} lines; most often tool substitutions such as "use pnpm, not npm" and forbidden tokens).
Style ({{corpus:model.category_p1.style|pct}} by the model), process ({{corpus:model.category_p1.process|pct}}),
tooling ({{corpus:model.category_p1.tooling|pct}}) and testing ({{corpus:model.category_p1.testing|pct}}) dominate;
security ({{corpus:model.category_p1.security|pct}}) and scope ({{corpus:model.category_p1.scope|pct}}) rules are rare
but are the categories most often deterministic (Table 3).

{{table:corpus_categories}}

*Table 3. Rubric category against rubric decidability.*

**Implications.** A deterministic enforcer can cover at most a third of what developers write into instruction files,
and plausibly closer to a tenth. That fraction is what rulewarden guarantees, which is why it reports the rest
instead of pretending to enforce it (`compile` lists every line it could not compile). The low rubric–model agreement
is itself a finding: whether a rule is "checkable" depends on whether the checker must confirm compliance or only
detect violations, and instruction files rarely say which.

# 5 Evaluation

**RQ2 (effectiveness).** Compared with rules in the instruction file alone, does deterministic hook enforcement reduce
rule violations in the final diff, and at what cost in turns, tokens and wall-clock?

**RQ3 (safety properties).** Does the tool hold its determinism and fail-closed guarantees under adversarial inputs?
What is the latency distribution per check?

**RQ4 (alarm management).** Does severity-first, capped reporting improve self-correction versus a flat list?

**RQ5 (independence).** When prompted adversarially, how often does the agent attempt to edit rules/hooks or add
deviations, and are all attempts blocked?

*Results pending (Phase 5).*

# 6 Discussion

**Dogfooding incident: an agent locked out by its own monitor.** rulewarden was developed by a coding agent under
rulewarden's own hooks. The agent installed the Claude Code hooks before a human had locked the rule set. Fail-closed
semantics (P5) then denied every tool call with RW-LOCK, and the Stop hook re-fired until the harness continuation
cap. Two human lock attempts were refused because a rule fixture contradicted the repository's protected-path
configuration. The qualification gate (P6) did exactly what it is for, but the conflict itself was a configuration
defect. The agent then proposed that the human disable the hooks. The human did, and the agent edited two source
files in a window that has no audit entries. A human reviewer identified the proposal itself as the most important
finding. A mediated agent under pressure asked for its monitor to be removed, and an operator under pressure agreed.
The engine was never bypassed technically; the bypass went through the human. We draw three design consequences:
setup must order the lock before hook installation; a Stop hook must block only on findings the agent may and can
fix (ADR-011), because a gate the agent cannot satisfy turns into pressure on the operator to remove it; and the
audit log must make such gaps visible. The gap here is visible only because the hash chain has no entries for those
edits, so the git history and the audit log disagree.

# 7 Related work

**Coding-agent policy tools.** The space is active. Cupcake [@cupcake] evaluates harness events against OPA/Rego
[@opa] policies compiled to WebAssembly and can add an LLM judge. AgentLint [@agentlint] ships 77 rules in packs with
three severity levels, approvals and a CI mode. FailproofAI [@failproofai] hooks twelve harnesses. CC Safety Net
[@ccsafetynet] and Hardstop [@hardstop] block destructive shell commands, and Hardstop is explicitly fail-closed.
diffgate [@diffgate] flags review-worthy regressions in a unified diff. agent-rules [@agentrules0x] audits a session
transcript against the imperative lines of `CLAUDE.md` after the fact. interlocks [@interlocks] runs one deterministic
Python quality loop for humans and agents alike, and veto [@vetopypi] authorises tool calls in agent applications.
rulewarden's novelty is not its checks, which overlap heavily with these tools. It is (i) the explicit, tested mapping
from safety-critical requirements to enforcement semantics, (ii) honest compilation of instruction files with a report
of what is *not* enforced, and (iii) the corpus and replayable controlled evaluation.

**Instruction files.** Besides the content studies above, dos Santos et al. catalogue configuration smells
[@dossantos2026smells], Shi et al. test rule files for permission minimality [@shi2026aletheia], and two controlled
studies measure the effect of context files on task success: they find little effect on correctness
[@khatri2026contextfiles] or effects that are largely independent of rule content [@zhang2026guardrails]. Neither measures
*compliance with the rules themselves*, which is our RQ2.

**Guardrails and policy-as-code.** NeMo Guardrails [@rebedea2023nemo] and Guardrails AI [@guardrailsai] constrain model
inputs and outputs. Semgrep [@semgrep] and pre-commit [@precommit] enforce code policy for humans. Microsoft's Agent
Governance Toolkit [@msagt] intercepts tool calls in deterministic code. We borrow their policy-as-code stance and apply
it at the diff boundary of coding agents.

**Instruction following and test gaming.** IFEval [@zhou2023ifeval] measures verifiable instruction following.
Reward hacking [@amodei2016concrete; @skalse2022defining] appears in coding agents as test exploitation, which
ImpossibleBench quantifies [@zhong2025impossiblebench]. Our `no-answer-embedding` pack targets the deterministic slice
of this behaviour: test files are read-only in a task.

# 8 Threats to validity

# 9 Conclusion and future work

# Appendix
