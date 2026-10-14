# Concepts

rulewarden's semantics come from safety-critical engineering. Each concept below is a requirement in the code,
with a test (the full mapping, P1–P12, is in §3 of the [paper](paper/index.html)).

## Decidability tiers (MISRA)

Every rule declares `decidability`:

| Tier | Meaning | Example | Effect |
|---|---|---|---|
| `deterministic` | Compliance is decided exactly on one diff or command by a bounded regex, path rule, syntax-tree query or plugin | "no `print()` in library code" | may block |
| `heuristic` | A check approximates compliance, with known false positives or negatives | "comments should not restate the code" | warns only; the schema rejects a blocking heuristic rule |
| `undecidable` | Needs intent or judgement | "write clean code" | listed, never evaluated |

The corpus study found that only a minority of the rules people write are deterministic in this sense, so
rulewarden reports what it does not enforce instead of pretending to.

## Severity (integrity levels)

`advisory` warns · `required` blocks · `critical` blocks and marks a violation of the monitor's independence
(for example a change to a protected path). A finding blocks only when the rule is `deterministic` **and**
`required` or `critical`, or when an engine error occurs on such a rule.

## Fail-closed, bounded execution

- Regexes are screened at load: nested unbounded quantifiers and backreferences are rejected (ReDoS).
- Inputs are capped (diff bytes, file bytes, line length). Content over a cap is reported as *could not verify*,
  which blocks for blocking rules. It is never silently passed.
- Content that git treats as binary (NUL bytes, UTF-16, UTF-32) is still scanned by regex rules, as extracted
  text.
- The whole evaluation runs in a forked child with a wall-clock budget. A timeout or crash is an engine error.
- An engine error on a blocking rule blocks; on an advisory rule it is reported and fails open.
- In Claude Code, the hooks use `onFailure: "block"`, so a crash of rulewarden itself denies the tool call.

## The lock and protected paths (independence)

`rules.lock` records the SHA-256 of every rule file and every **protected path**: by default `rules/**`,
`rules.lock`, `.rulewarden/**`, `.claude/settings.json`, `.claude/settings.local.json`,
`.pre-commit-config.yaml`, `.github/workflows/**`, `.opencode/**`, `.codex/**`, `.gemini/**` and
`.git/hooks/**` (extend it with `protected:` in `.rulewarden/config.yaml`). Then:

- a rule set that does not match the lock fails closed (`RW-LOCK`) until a human locks again;
- a change to a protected path is a critical finding unless its content equals what a human locked;
- `lock` refuses to write unless every fixture passes, so a valid lock certifies a qualified rule set.

So a human's legitimate change is "edit, then lock", and an agent's change is never locked.

## Qualification (DO-330)

A rule without at least one failing and one passing fixture is invalid and does not load. `test-rules` runs
all fixtures; CI runs them; editing a rule means a regression run.

## Deviations (MISRA)

An inline comment exempts one line from one rule (rule `R-012` here is illustrative):

```python
# rulewarden: deviate R-012 reason="vendor script, no jq on target" approved-by="@alice" expires=2027-06-30
```

- The approver must be listed in the protected `.rulewarden/approvers` file. Expired deviations count as
  violations.
- For `advisory` rules, a valid comment is enough.
- For `required` and `critical` rules, the deviation line must also be registered in `rules.lock` by a human
  `lock`. An agent-authored deviation of a blocking rule is itself a critical finding (`RW-DEVIATION`).

## Alarm management (ISA-18.2)

Reports are severity-first with a stable order (path, line, rule id). Identical findings are deduplicated,
advisory findings are capped (5 by default), the total length is capped (2,000 characters by default) so the
agent's context is not flooded, and every finding carries exactly one imperative `Fix:` line. Set
`report.style: flat` to get an unordered, uncapped list.

## Audit and traceability

Every run appends to `.rulewarden/audit.jsonl`, keyed by diff hash and rule-set hash. Each line carries the
SHA-256 of the previous one, so an edited, removed or reordered line breaks the chain. `rulewarden report`
verifies the chain and renders the log. `rulewarden stats` derives near-miss metrics: violations per rule,
self-correction cycles, and rules that never fire.

## Exit codes

`0` pass, or advisory findings only · `1` blocking findings · `3` engine or configuration error.
Harness adapters map these onto each harness's own semantics. Claude Code, for example, treats exit code 1
as fail-open, so the adapter answers with exit 0 plus a JSON decision, or with exit 2.
