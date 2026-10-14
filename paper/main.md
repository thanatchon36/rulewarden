---
title: "rulewarden: Deterministic Runtime Assurance for AI Coding Agents"
subtitle: "Borrowing Safety-Critical Systems Engineering to Enforce Agent Instruction Files"
---

# Abstract

*(Written last; every claim maps to an RQ result.)*

# 1 Introduction

# 2 Background

## 2.1 Agent instruction files and harness hooks

## 2.2 Safety-critical concepts P1–P12

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

# 7 Related work

# 8 Threats to validity

# 9 Conclusion and future work

# Appendix
