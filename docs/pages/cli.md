# CLI reference

Generated from `rulewarden <command> --help` by `docs/gen_reference.py`.

Exit codes: `0` pass or advisory findings only · `1` blocking findings · `3` engine or configuration error.

## rulewarden

```text
Usage: rulewarden [OPTIONS] COMMAND [ARGS]...

  Deterministic runtime assurance for AI coding agents.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  check       Run the rules on a change; exit 0 pass, 1 blocked, 3 engine error.
  compile     Instruction file → rule proposals, plus every line that could not be compiled and...
  doctor      Verify installation, hook wiring, lock integrity and determinism.
  hook        Harness adapter entry point (reads the harness's JSON or git arguments).
  init        Detect instruction files, vendor packs, compile rules, install hooks.
  lock        Qualify the rule set and write rules.lock (a human action; hooks block agents...
  report      Render the audit log (and optionally a framework evidence summary).
  stats       Near-miss and self-correction metrics from the audit log (P10).
  test-rules  Run every rule's fixtures (tool qualification, P6).
```

## rulewarden check

```text
Usage: rulewarden check [OPTIONS]

  Run the rules on a change; exit 0 pass, 1 blocked, 3 engine error.

Options:
  --root DIRECTORY        Repository root (default: git toplevel).
  --staged                Check the index against HEAD.
  --working-tree          Check the working tree against the baseline (default).
  --diff FILE             Check a unified diff file ('-' for stdin).
  --base TEXT             Baseline revision (default: session baseline, then config, then HEAD).
  --range TEXT            Check BASE...HEAD (CI mode), e.g. origin/main...HEAD.
  --command TEXT          Check a shell command against command-scope rules.
  --format [text|json]
  --style [managed|flat]
  --all                   Show every finding (no advisory or length cap).
  --json-out FILE         Also write the JSON report here.
  --as-of [%Y-%m-%d]      Date for deviation expiry (default: today UTC).
  --no-audit              Do not append to the audit log.
  --harness TEXT          Harness name recorded in the audit log.
  --help                  Show this message and exit.
```

## rulewarden compile

```text
Usage: rulewarden compile [OPTIONS] INSTRUCTION_FILE

  Instruction file → rule proposals, plus every line that could not be compiled and why.

Options:
  --root DIRECTORY
  --out FILE            Write proposed rules here (YAML).
  --format [text|json]
  --help                Show this message and exit.
```

## rulewarden doctor

```text
Usage: rulewarden doctor [OPTIONS]

  Verify installation, hook wiring, lock integrity and determinism.

Options:
  --root DIRECTORY
  --determinism-only  Run only the determinism self-test.
  --help              Show this message and exit.
```

## rulewarden hook

```text
Usage: rulewarden hook [OPTIONS] {claude-code|git|pre-commit|ci|codex|gemini|opencode} [ARGS]...

  Harness adapter entry point (reads the harness's JSON or git arguments).

Options:
  --root DIRECTORY
  --help            Show this message and exit.
```

## rulewarden init

```text
Usage: rulewarden init [OPTIONS]

  Detect instruction files, vendor packs, compile rules, install hooks.

  Agent-harness hooks (Claude Code, OpenCode) are installed only together with --lock, between two
  lock writes, so they never run without a lock (ADR-013).

Options:
  --root DIRECTORY
  --packs TEXT                  Comma-separated starter packs to vendor.  [default: protected-
                                set,scope,secrets,no-answer-embedding,hygiene-python,shell-
                                tooling,voice]
  --claude / --no-claude        Install Claude Code hooks into .claude/settings.json.
  --git-hooks / --no-git-hooks  Install plain git hooks.
  --opencode                    Install the OpenCode plugin.
  --binary TEXT                 Path of the rulewarden executable the hooks call.
  --lock / --no-lock            Also lock (human action; needs a TTY or --ci).
  --hooks-only                  Only install hooks (after locking); do not vendor packs or compile.
  --help                        Show this message and exit.
```

## rulewarden lock

```text
Usage: rulewarden lock [OPTIONS]

  Qualify the rule set and write rules.lock (a human action; hooks block agents from running it).

Options:
  --root DIRECTORY
  --ci              Allow running without a TTY (scripted setup by a human).
  --check           Only verify the existing lock; exit 1 if it is stale.
  --help            Show this message and exit.
```

## rulewarden report

```text
Usage: rulewarden report [OPTIONS]

  Render the audit log (and optionally a framework evidence summary).

Options:
  --root DIRECTORY
  --format [markdown|json]
  --framework [nist-ai-rmf]  Map the evidence to a governance framework (v3).
  --limit INTEGER            Most recent audit entries to list.
  --help                     Show this message and exit.
```

## rulewarden stats

```text
Usage: rulewarden stats [OPTIONS]

  Near-miss and self-correction metrics from the audit log (P10).

Options:
  --root DIRECTORY
  --format [text|json]
  --help                Show this message and exit.
```

## rulewarden test-rules

```text
Usage: rulewarden test-rules [OPTIONS]

  Run every rule's fixtures (tool qualification, P6).

Options:
  --root DIRECTORY
  --path TEXT       Rule file or directory (default: configured rule paths).
  -v, --verbose
  --help            Show this message and exit.
```

