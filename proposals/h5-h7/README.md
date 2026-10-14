# Proposal: NEEDS_HUMAN H5, H6, H7

Prepared by the agent; **a human reviews `human.patch`, applies it and locks**. The agent cannot edit these files
(they are protected), and it does not lock.

| Item | Change in `human.patch` |
|---|---|
| H6 | `rules/packs/protected-set.yaml`, PRT-002: `\brules/` becomes `(?<![\w./-])(\./)?rules/`, so `bench/rules/…` no longer matches while `rules/…`, `./rules/…`, quoted paths and `>rules/…` still do. New pass fixture `cp a.yaml bench/rules/x.yaml`. The shipped pack in `src/rulewarden/packs/` already has the same change (agent commit). |
| H5 | `rules/packs/scope.yaml`, SCP-001: allow `.pre-commit-hooks.yaml`; the patch also creates that manifest (copy of `pre-commit-hooks.yaml` here). |
| H7 | `.claude/settings.json`: the four hook commands call `~/.local/bin/rulewarden` (a separately installed, non-editable build) instead of the editable `.venv` copy, so editing `src/` cannot change the running monitor (ADR-015). |

Verification done by the agent (on copies, never on the protected files): `git apply --check` passes; the patched
packs pass all fixtures (121); `probe_prt002.py` checks 12 extra commands, all as intended.

## Apply (one line, from the repository root)

The order matters: install the pinned binary first, so the hooks never point at a missing program.

```bash
uv tool install --force --from . rulewarden && ~/.local/bin/rulewarden --version \
  && git apply proposals/h5-h7/human.patch && rm -r bench/rules \
  && uv run --frozen rulewarden test-rules && uv run --frozen rulewarden lock --ci \
  && uv run --frozen python -c "from pathlib import Path; from rulewarden.adapters import git_hook; git_hook.install(Path('.'), str(Path.home() / '.local/bin/rulewarden'))" \
  && ~/.local/bin/rulewarden doctor
```

To update the pinned monitor later (after reviewing new engine changes): `uv tool install --force --from . rulewarden`.

## Roll back (if anything fails before the lock)

```bash
git checkout -- rules/packs/protected-set.yaml rules/packs/scope.yaml .claude/settings.json && rm -f .pre-commit-hooks.yaml
```
