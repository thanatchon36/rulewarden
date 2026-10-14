# Contributing

rulewarden is a monitor for coding agents, so it has to be simpler and more predictable than the thing it
watches. Most of the rules below follow from that.

By contributing you agree that your contribution is licensed under Apache-2.0.

## The rules that are not negotiable

1. **No model in the enforcement path.** A check is a regex, a glob, a Python AST walk, a jq filter, an
   allowlisted command or a local plugin. The same diff and rule set must give a byte-identical report on every
   machine (`rulewarden doctor --determinism-only`).
2. **Fail closed.** An engine error, a timeout or an oversized input on a blocking rule is a block with a
   *could not verify* finding, never a silent pass.
3. **Every rule ships with fixtures:** at least one content, path or command that must fail and one that must
   pass. A rule without both does not load.
4. **Only `deterministic` rules may block.** A rule that needs judgement is `heuristic` (advisory) or
   `undecidable` (listed, never evaluated). Do not promote a heuristic to blocking to make a number look better.
5. **Report what is not enforced.** If `compile` cannot turn an instruction-file line into a check, it says so.
6. **No hand-typed numbers in the paper or README.** They come from generated result files; `make paper` fails on
   an unresolved placeholder or an unverified citation.

## Setup

```bash
git clone https://github.com/thanatchon36/rulewarden && cd rulewarden
uv sync --all-groups
make check          # lint, mypy --strict, tests with coverage, rule fixtures, determinism, self-check
```

Before every commit: `make check`. Before a pull request that touches the benchmark, the paper or the docs:
`make ci`.

## What is most useful to contribute

### A rule

Add it to the starter pack it belongs to under `src/rulewarden/packs/`, with fixtures, and run
`rulewarden test-rules --path src/rulewarden/packs`. The [rule-writing guide](docs/pages/writing-rules.md) lists
the engines and their parameters. In the pull request, quote the instruction-file wording the rule enforces and
say which tier it is and why.

### A false-positive report

The most valuable bug report is a diff that rulewarden blocked and should not have. Include the diff (or a minimal
one), the rule ID, the report line and the command you ran. The benchmark's own false positive (amendment A1 in
`bench/ANALYSIS_PLAN.md`) is the worked example.

### An adapter

Adapters live in `src/rulewarden/adapters/`. An adapter reads the harness's hook payload, turns it into a proposed
change, and maps the verdict back to the harness's deny/allow format. It must deny on any parse error, and it must
not let the agent reach a protected path through a different tool (for example a shell redirect instead of an
Edit).

## Code standards

- Python 3.11+, type hints throughout; `ruff format`, `ruff check` and `mypy --strict` must pass.
- No bare `except`; no `print()` in `src/` (use `logging`).
- Docstrings of at most 8 lines; comments say why, not what.
- Tests for every change. Coverage must stay at 90% or more (`make cov`).
- Never edit an existing test to make it pass. Add new tests in new files or new functions.
- A new runtime dependency needs an entry in `DECISIONS.md`. There are two today, and that is deliberate.
- Generated files are generated: `paper/paper.md`, `paper/paper.pdf`, `docs/pages/paper/`,
  `docs/pages/cli.md`, `docs/pages/rules.md` and the findings block in `README.md` have staleness tests. Edit
  the source (`paper/main.md`, the CLI, the packs, the result files), then run `make paper docs`. The PDF and
  the web reader need pandoc 3.x; the `typst` wheel in the `paper` group bundles the compiler.

## Changing the benchmark or the paper

The benchmark is pre-registered in `bench/ANALYSIS_PLAN.md`. Do not change a hypothesis, metric or threshold to
change a verdict. A change made after the runs goes in as a dated amendment that says what changed and why, and
the original wording stays. Null results and tool defects are reported; a pull request that removes one will be
declined. `make replay` must reproduce every number from the recordings without an API key.

## Reporting a security issue

rulewarden reads untrusted diffs, hook payloads and rule files. If you find a way for an agent to get a change past
a blocking rule, edit a protected path, or run code through a rule, please open a private security advisory on
GitHub rather than a public issue. See [`docs/security.md`](docs/security.md) for the threat model.

## Pull requests

Small, tested, one topic. Use Conventional Commits. In the description, say which rules or adapters changed,
whether any generated file was regenerated, and paste the `make check` result.
