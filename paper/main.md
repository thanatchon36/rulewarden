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

# 4 Corpus study (RQ1)

**RQ1.** What fraction of rules in real-world agent instruction files is deterministically checkable, heuristic, or
undecidable, and what rule categories dominate?

*Results pending (Phase 4).*

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
