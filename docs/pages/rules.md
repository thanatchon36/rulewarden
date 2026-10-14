# Rule catalogue

The 7 starter packs ship 26 rules. Generated from `src/rulewarden/packs/` by
`docs/gen_reference.py`. Every rule has at least one failing and one passing fixture;
`rulewarden test-rules --path <pack dir>` runs them. Only `deterministic` rules with severity
`required` or `critical` block; `heuristic` rules warn; `advisory` findings never block.

## `hygiene-python`

Python code hygiene that agents commonly violate. Deterministic rules block; heuristics only warn.

| ID | Rule | Severity | Tier | Engine | Fix |
|---|---|---|---|---|---|
| `HYG-001` | No bare except | required | deterministic | ast | Catch a specific exception type, e.g. `except ValueError:`. |
| `HYG-002` | No print() in library code | required | deterministic | ast | Use the logging module instead of print(), e.g. `logger.info(...)`. |
| `HYG-003` | TODO without an issue reference | required | deterministic | regex | Link the TODO to an issue, e.g. `# TODO(#123): ...`, or do the work now. |
| `HYG-004` | Docstring longer than 8 lines | required | deterministic | ast | Shorten the docstring to at most 8 lines; move detail to docs/. |
| `HYG-005` | Comment density too high in added code | advisory | heuristic | python | Remove comments that describe what the code does; keep the ones that say why. |
| `HYG-006` | Comment restates the code on the next line | advisory | heuristic | python | Delete the comment or make it say why, not what. |
| `HYG-007` | Broad exception silently swallowed | advisory | deterministic | ast | Handle or re-raise the exception; at minimum log it. |

## `no-answer-embedding`

Keep agents from making tests pass by changing the tests or hard-coding expected outputs (claude-code #319; ImpossibleBench, arXiv:2510.20270). Path policy is deterministic; the literal-lookup detector is a heuristic and only warns.

| ID | Rule | Severity | Tier | Engine | Fix |
|---|---|---|---|---|---|
| `NAE-001` | Existing test modified | critical | deterministic | glob | Revert the change to the test; tests are read-only in this task. Fix the code under test. |
| `NAE-002` | Test skipped or marked expected-to-fail | required | deterministic | regex | Remove the skip/xfail marker and make the test pass by fixing the code. |
| `NAE-003` | Function returns hard-coded results for literal inputs | advisory | heuristic | python | Compute the result from the input instead of special-casing the test values. |

## `protected-set`

P2 independence: the agent cannot change its own monitor. Protected paths come from the config (defaults: rules/, rules.lock, .rulewarden/, .claude/settings*.json, .pre-commit-config.yaml, .github/workflows/, .opencode/, .codex/, .gemini/, .git/hooks/). A change is allowed only when its content is exactly what a human recorded with `rulewarden lock`.

| ID | Rule | Severity | Tier | Engine | Fix |
|---|---|---|---|---|---|
| `PRT-001` | Protected path changed | critical | deterministic | glob | Revert this change; a human must apply it and run `rulewarden lock`. |
| `PRT-002` | Shell command writes to a protected path | critical | deterministic | regex | Do not modify protected files from the shell; ask a human to make the change. |
| `PRT-003` | Agent runs a human-only rulewarden command or disables hooks | critical | deterministic | regex | Only a human may lock rules or change hook wiring; report the situation instead. |

## `scope`

Where the agent may write and which git operations it may run. SCP-001's allowed paths are a starting point; edit them for your project before locking.

| ID | Rule | Severity | Tier | Engine | Fix |
|---|---|---|---|---|---|
| `SCP-004` | Git hooks bypassed with --no-verify | critical | deterministic | regex | Run the commit without --no-verify and fix what the hooks report. |
| `SCP-005` | Force push | critical | deterministic | regex | Push without force; integrate the remote changes instead. |
| `SCP-006` | Git history rewrite | critical | deterministic | regex | Make a new commit instead of rewriting history. |
| `SCP-007` | Recursive delete outside the repository | critical | deterministic | regex | Delete only paths inside the repository, and name them explicitly. |
| `SCP-001` | Change outside the allowed paths | required | deterministic | glob | Revert the change; this task may only modify the allowed paths. |
| `SCP-002` | New or changed dependency without a recorded decision | required | deterministic | regex | Record why the dependency is needed in DECISIONS.md in the same change, or remove it. |
| `SCP-003` | Test file deleted | required | deterministic | glob | Restore the deleted test; fix the code under test instead. |
| `SCP-008` | New or changed requirement without a recorded decision | required | deterministic | regex | Record why the dependency is needed in DECISIONS.md in the same change, or remove it. |

## `secrets`

Common credential formats. The fixtures are synthetic strings built to match the patterns (all-zero or EXAMPLE bodies); they are not real credentials.

| ID | Rule | Severity | Tier | Engine | Fix |
|---|---|---|---|---|---|
| `SEC-001` | Credential or private key in the change | critical | deterministic | regex | Remove the credential from the change, rotate it, and load it from the environment or a secret store. |

## `shell-tooling`

Tooling conventions for shell scripts.

| ID | Rule | Severity | Tier | Engine | Fix |
|---|---|---|---|---|---|
| `SH-002` | Piping a download into a shell | critical | deterministic | regex | Download the script to a file, verify its checksum, then run it. |
| `SH-001` | Use jq, not Python, for JSON in shell scripts | required | deterministic | regex | Replace the Python one-liner with jq. Example: jq -r '.key' file.json |
| `SH-003` | sudo in a script | required | deterministic | regex | Remove sudo; document the privileged step for a human instead. |

## `voice`

Filler phrases and verbal tics in comments, docstrings, markdown and commit messages. The default list is deliberately short and editable; see claude-code issues #53454 and #65961 for motivation.

| ID | Rule | Severity | Tier | Engine | Fix |
|---|---|---|---|---|---|
| `VOI-001` | Filler phrase in prose | advisory | deterministic | regex | Delete the filler phrase and state the point directly. |

