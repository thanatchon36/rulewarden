# Writing rules

Rules live in YAML files under `rules/` (configurable). `src/rulewarden/engine/schema.py` is the source of
truth; this page summarises it.

## A complete rule

```yaml
version: 1
rules:
  - id: R-012                          # stable, never reused
    title: Use jq, not Python, for JSON in shell scripts
    source: CLAUDE.md:L14              # traceability: where the rule came from
    severity: required                 # advisory | required | critical
    decidability: deterministic        # deterministic | heuristic | undecidable
    scope: diff                        # diff | file | repo | command
    applies_to: ["**/*.sh", "**/*.bash"]
    exclude: ["vendor/**"]
    check:
      engine: regex
      on: added_lines
      pattern: 'python3?\s+-c\s+.*\bjson\b'
    message: "Replace the Python one-liner with jq, e.g. jq -r '.key' file.json"
    fixtures:                          # both lists non-empty, or the rule will not load
      fail: ["python3 -c 'import json,sys; print(json.load(sys.stdin)[\"k\"])' < f.json"]
      pass: ["jq -r '.k' f.json"]
    deviations: allowed                # allowed | forbidden
    tags: [shell, tooling]
```

Required keys: `id`, `title`, `severity`, `decidability`, `message`. An `undecidable` rule has no `check` and
no fixtures; it is listed and never evaluated. A `heuristic` rule must be `advisory`.

## Paths

Globs are matched against the repository-relative POSIX path. `**/` matches zero or more directories, `*` does
not cross `/`, and a pattern without `/` matches the basename at any depth. `applies_to` defaults to
everything.

## `check.on`

| Value | Evaluated on | Engines |
|---|---|---|
| `added_lines` | each added line of the diff | regex (default for regex) |
| `hunks` | each block of consecutive added lines | regex |
| `file` | the whole new file content | regex, ast, jq, shell, python |
| `path` | the path and its change status | glob (default for glob), regex |
| `command` | a shell command the agent is about to run (`scope: command`) | regex, shell |

## Engines

| Engine | Parameters | Notes |
|---|---|---|
| `regex` | `pattern` or `patterns`, `flags` (`i m s x`), `mode` (`forbid` default, or `require` with `on: file`/`command`), `within` (`all`, `comments`, `code`), `unless`, `unless_changed` | ReDoS-screened at load; `within: comments` understands Python and shell comments and docstrings |
| `glob` | `paths` or `paths_from: protected`, `mode` (`forbid` or `allow`), `change` (`added`, `modified`, `deleted`, `renamed`), `exempt_if_locked`, `unless_changed` | path policy: protected paths, allowed paths, read-only tests |
| `ast` | `rule`: `bare-except`, `broad-except-pass`, `call` (`names`), `import` (`names`), `docstring-max-lines` (`max`), `function-max-lines` (`max`) | Python only; a file that does not parse is *could not verify* |
| `jq` | `filter` | each `true` or string output is a finding; needs `jq` on `PATH` (refused if it resolves inside the repository) |
| `shell` | `argv` | opt-in in `.rulewarden/config.yaml`; allowlisted binaries only; no shell; see [Security](security.md) |
| `python` | `plugin` (`hygiene.comment_density`, `hygiene.restating_comment`, `answers.literal_lookup`, or `local:<file>:<function>` under `.rulewarden/plugins/`), `options` | local plugins are code and live under a protected path |

`unless_changed: [globs]` suppresses a finding when another file matching the globs changed in the same
change set. For example, "dependency manifest changed" is allowed when `DECISIONS.md` changed too.

## Fixtures

A fixture is file content (for `added_lines`, `hunks` and `file`), a path (for `path`, optionally
`{path: x, status: added}`) or a command (for `command`). Fixtures in `fail` must produce at least one finding,
and those in `pass` must produce none. Run them with:

```bash
rulewarden test-rules              # the configured rule set
rulewarden test-rules --path dir/  # any directory of rule files
```

## After editing

Run `test-rules`, then a human runs `rulewarden lock`. Until then every check fails closed with `RW-LOCK`.
