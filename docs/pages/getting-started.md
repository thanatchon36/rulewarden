# Getting started

## Install

```bash
pip install rulewarden      # or: uv tool install rulewarden
rulewarden --version
```

Python 3.11 or newer. Runtime dependencies: PyYAML and Click. `jq` on `PATH` is needed only for rules
that use the `jq` engine.

## Set up a repository

The order matters. Agent hooks are fail-closed: without a valid `rules.lock` they deny **every** tool call.

```bash
cd your-repo
rulewarden init                       # 1. vendor starter packs, compile CLAUDE.md/AGENTS.md, install git hooks
#                                       2. a human reviews rules/ and edits until it says what you mean
rulewarden test-rules                 # 3. every fixture must pass
rulewarden init --hooks-only --lock   # 4. lock, install the Claude Code hooks, lock again
rulewarden doctor                     # 5. wiring, lock, audit chain, determinism self-test
```

`init` without `--lock` never installs agent hooks. With `--lock`, it locks first (and stops if a fixture
fails), installs the hooks, then locks again because the hook files are themselves protected.

## Check a change by hand

```bash
rulewarden check                      # working tree against the baseline (HEAD or the session start)
rulewarden check --staged             # what you are about to commit
rulewarden check --range origin/main...HEAD
rulewarden check --command "git push --force"
rulewarden check --format json        # canonical JSON, byte-identical for identical input
```

## Change a rule

1. Edit the YAML under `rules/` (see [Writing rules](writing-rules.md)).
2. `rulewarden test-rules`: the rule must have a failing and a passing fixture, and all fixtures must pass.
3. `rulewarden lock`. Until you do, every check fails closed with `RW-LOCK`.

Only a human runs `lock`. It needs an interactive terminal (or `--ci` in a script a human runs), and the
agent hook denies the command outright.

## Compile an instruction file

```bash
rulewarden compile CLAUDE.md --out rules/compiled-claude-md.yaml
```

`compile` matches instruction-file lines against a library of rule templates and reports every line it
could not compile, labelled `heuristic-candidate` or `undecidable`, so you can see exactly what is *not*
enforced.
