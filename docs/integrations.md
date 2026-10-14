# Integrations

rulewarden's core is harness-agnostic: a diff or command goes in, a report and an exit code come out. Each adapter
maps that onto one harness's hook contract. The contracts were verified on 2026-10-14 and are recorded in
`research/harness-apis.md`. Defence in depth is intentional:

| Layer | When it runs | Can the agent bypass it? | Role |
|---|---|---|---|
| Agent hook (Claude Code, OpenCode, Codex, Gemini) | before each tool call | only through a misconfigured harness | immediate feedback, denies before actuation |
| git hooks (`pre-commit`, `commit-msg`, `pre-push`) | on commit and push | `--no-verify`, which the agent hook denies | works with any agent, or none |
| CI (`rulewarden hook ci`) | on every pull request | no | final gate |

## Setup order (read this first)

Agent hooks are fail-closed. Without a valid `rules.lock` they deny **every** tool call, which freezes the agent
session (this happened while building rulewarden; see `DECISIONS.md` ADR-010 and ADR-013). So:

1. `rulewarden init` vendors the starter packs, compiles your instruction file into `rules/compiled-*.yaml`,
   installs the git hooks, and does **not** install agent hooks.
2. A human reviews `rules/`, runs `rulewarden test-rules`, and edits until every fixture passes.
3. A human runs `rulewarden init --hooks-only --lock`. This locks, installs the agent hooks, and locks again so the
   lock also covers the hook files, which are protected paths. If the first lock fails, no agent hook is written.
4. `rulewarden doctor` checks the wiring, the lock, the audit chain and determinism. It reports a `FAIL` if agent
   hooks are installed without a valid lock.

Every later change to `rules/`, `.rulewarden/`, `.claude/` or the other protected paths needs a human lock.

## Claude Code

`init --hooks-only --lock` merges these hooks into `.claude/settings.json`, keeping existing hooks:

| Event | What rulewarden does |
|---|---|
| `SessionStart` | records the baseline (a snapshot of the tree plus untracked-file hashes) |
| `PreToolUse` on `Bash` | checks the command against command-scope rules (`--no-verify`, force-push, history rewrite, `rm -rf` outside the repo, human-only commands) and denies it |
| `PreToolUse` on `Edit\|Write\|NotebookEdit` | computes the proposed file content, checks it as a diff, and denies the edit before anything is written |
| `PostToolUse` | checks the working tree against the session baseline; blocking findings go back to the agent next to the tool result |
| `Stop` | warning gate (ADR-011): blocks only on findings introduced in this session that the agent may fix; never blocks twice in a row; leftovers are recorded in `NEEDS_HUMAN.md` and the audit log |

`PreToolUse` and `PostToolUse` use `onFailure: "block"`, so a crash or timeout of rulewarden blocks the call instead
of letting it through. Exit code 1 is fail-open in Claude Code, so the adapter always answers with exit 0 plus a JSON
decision, or exit 2.

Observed behaviour: hooks written to `.claude/settings.json` during a running session took effect in that session
(Claude Code 2.1.299). The docs do not promise this, which is the reason for the setup order above.

## git hooks and the pre-commit framework

`rulewarden init` writes `.git/hooks/pre-commit` (staged diff), `commit-msg` (message prose), and `pre-push` (the
pushed range, including new branches). Each one is a two-line script that runs `rulewarden hook git <name>`.

With the [pre-commit](https://pre-commit.com) framework, use a local hook in `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: rulewarden
        name: rulewarden (staged changes)
        entry: rulewarden hook git pre-commit
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
      - id: rulewarden-commit-msg
        name: rulewarden (commit message)
        entry: rulewarden hook git commit-msg
        language: system
        stages: [commit-msg]
```

A `.pre-commit-hooks.yaml` manifest, which lets other repositories use `repo: https://github.com/…/rulewarden`, is
waiting on a human scope change (`NEEDS_HUMAN.md` H5).

## CI (GitHub Actions)

```yaml
name: rulewarden
on: pull_request
permissions:
  contents: read
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install rulewarden==0.1.0  # not on PyPI yet (NEEDS_HUMAN.md H3); until then install from git
      - run: rulewarden lock --check
      - run: rulewarden hook ci "origin/${{ github.base_ref }}"
```

`hook ci` checks `BASE...HEAD`, prints GitHub `::error` annotations, and exits 1 on blocking findings. Protect the
workflow file and `rules.lock` with CODEOWNERS, because the lock cannot vouch for itself without a mediating harness.

## OpenCode

`init --hooks-only --lock --opencode` writes `.opencode/plugins/rulewarden.js`. Its `tool.execute.before` hook
pipes the tool call to `rulewarden hook opencode` and throws on a deny, which blocks the call. If the hook process
crashes or prints something that is not JSON, the plugin also throws (fail-closed). Only pre-tool checks
are mapped; the git hooks and CI cover the end of the turn.

## Codex CLI and Gemini CLI

`rulewarden hook codex` and `rulewarden hook gemini` translate those harnesses' pre-tool JSON (Codex `apply_patch`
and shell; Gemini `write_file`, `replace`, `run_shell_command`) to the same handler. Configure them by hand, following
`research/harness-apis.md`. Both harnesses treat hook crashes and timeouts as fail-open, and Codex project hooks load
only for trusted projects. Treat these adapters as early feedback, and rely on the git hooks and CI as the gates.
