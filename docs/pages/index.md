# rulewarden

**Deterministic runtime assurance for AI coding agents.** rulewarden turns the rules in `CLAUDE.md` and
`AGENTS.md` into checks that run on every change an agent makes, in a pre-tool hook, a git hook and CI.
It fails closed.

[Get started](getting-started.md){ .md-button .md-button--primary }
[Read the paper](paper/index.html){ .md-button }
[Rule catalogue](rules.md){ .md-button }

## Why

Instruction files are context, not controls. An agent reads "never edit the tests" or "no `print()` in
library code" and usually complies, but nothing checks that it did. rulewarden borrows the answer
safety-critical engineering gives for a capable controller that cannot be verified: wrap it in a *simple*
monitor that can be.

- **Deterministic.** No model in the enforcement path. The same diff and rule set produce a byte-identical
  report on every machine.
- **Honest about coverage.** Every rule declares a decidability tier. Only `deterministic` rules may block;
  `heuristic` rules warn; `undecidable` rules are listed and never evaluated. `rulewarden compile` reports
  which lines of your instruction file it could *not* turn into a check.
- **Self-protecting.** The rule set, its lock and the hook wiring are protected paths. An agent cannot
  weaken its own monitor; a human reviews and runs `rulewarden lock`.
- **Qualified rules.** A rule without a passing and a failing fixture does not load.
- **Readable reports.** Severity first, deduplicated, capped, exactly one `Fix:` line per finding.

## Defence in depth

| Layer | When | Bypassable by the agent? | Role |
|---|---|---|---|
| Agent hook (Claude Code, OpenCode, Codex, Gemini CLI) | before each tool call | only through a misconfigured harness | denies a change before it is written |
| git hooks (`pre-commit`, `commit-msg`, `pre-push`) | on commit and push | `--no-verify`, which the agent hook denies | works with any agent, or none |
| CI (`rulewarden hook ci`) | on every pull request | no | final gate |

## A report

```text
BLOCKED — 1 required, 0 advisory
[B-DOCSTRING required] src/textkit/slug.py:37 Docstring longer than 5 lines (docstring has 6 lines (max 5)) — Fix: Shorten the docstring to at most 5 lines.
```

This one is real: recorded in the benchmark run `T01-slugify/C-r1`. The agent's next write had a
5-line docstring and passed.

## What the research found

rulewarden ships with a [paper](paper/index.html), a [corpus study](research/corpus.md) of public instruction
files and a pre-registered [benchmark](research/benchmark.md). In short: only a minority of the rules people
write can be decided on a diff, which is why rulewarden reports what it does *not* enforce; and on small
tasks a strong model rarely broke the rules at all, so the hooks' value showed up mid-session and in
dogfooding rather than in the final diffs.
