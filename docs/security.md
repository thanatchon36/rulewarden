# Security model

## Threat model

The agent is **untrusted but mediated**: every write and every shell command passes through a harness hook that
runs rulewarden. The agent may make mistakes, cut corners, or try to make checks pass by changing the checks.
rulewarden defends the rule set, the lock, the hook wiring and the CI configuration (protected paths), and it fails
closed on errors in blocking rules.

Out of scope, and listed as limitations:
- A harness that does not run the hooks, or ignores `onFailure: "block"` (for example Codex and Gemini CLI treat hook
  crashes as fail-open). The git hooks and CI are the backstop.
- A human who disables the hooks. This happened during development (`DECISIONS.md` ADR-010); the hash-chained audit
  log makes such a gap visible but cannot prevent it.
- Running the monitor from the same working copy the agent edits (ADR-015). Install a pinned build for the hooks.
- `rules.lock` cannot vouch for itself without a mediating harness. Without one, protect it with CODEOWNERS and CI.

## Engines

| Engine | Executes | Isolation |
|---|---|---|
| `regex` | Python `re` in-process | Static ReDoS screen (nested unbounded quantifiers and backreferences rejected at load), input caps, and the whole evaluation runs in a forked child with a wall-clock budget |
| `glob` | path matching | none needed |
| `ast` | Python `ast.parse` on the content | input caps; parse errors on blocking rules are *unverifiable* findings, which block |
| `jq` | the `jq` binary | resolved on `PATH`, but refused if the resolved binary lies inside the repository (an agent could otherwise plant one); minimal environment; per-check timeout |
| `shell` | an allowlisted binary | **opt-in** (`engines.shell` in the protected config); binary looked up only on `/usr/bin:/bin`; no shell; argv from the locked rule file; scrubbed environment with a temporary `HOME`/`TMPDIR` as working directory; per-check timeout |
| `python` | built-in plugins, or local plugins under `.rulewarden/plugins/` | built-ins are part of the package. Local plugins are arbitrary code and therefore live under a protected path, so an agent cannot add or change one without a human lock |

**Not provided:** OS-level sandboxing (no network namespace, seccomp or filesystem jail) for `shell` and `jq`. A
human who allowlists a binary for the shell engine trusts that binary with the user's privileges, network included.

## Reporting

Report security issues privately to the repository owner rather than in a public issue.
