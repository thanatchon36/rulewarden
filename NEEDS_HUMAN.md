# NEEDS_HUMAN.md

Actions the agent must not take on its own (irreversible, costs money, or legal exposure). Each item says what, why,
and the exact command or file to review. The agent keeps working on everything else.

| # | Item | Why it needs a human | How |
|---|---|---|---|
| H1 | Confirm the name `rulewarden` (ADR-001) | Naming is sticky once public/published | Rename = search/replace before going public |
| H2 | Flip GitHub repo to public (ADR-004) | Publishing is irreversible; corpus excerpts and transcripts carry licence exposure | Review `corpus/data/`, `bench/recorded/`, then `gh repo edit thanatchon36/rulewarden --visibility public --accept-visibility-change-consequences` |
| H3 | Publish to PyPI | §0.3: the human releases | Configure trusted publisher on PyPI for `.github/workflows/release.yml`, then push tag `v0.1.0` |
| H4 | Push local commits to `origin` | `git push` is denied by this session's permission settings (the first push during `gh repo create` went through; later pushes were refused 2026-10-14). The agent commits locally and does not try to get around the denial | `git push origin main` (and `git push --tags` if a tag exists) |
| H5 | Add a `.pre-commit-hooks.yaml` manifest so other repositories can use `repo: https://github.com/thanatchon36/rulewarden` | The file is outside SCP-001's allowed paths (a protected rule) | Add `".pre-commit-hooks.yaml"` to SCP-001 `paths` in `rules/packs/scope.yaml`, lock, then create the manifest with hooks `rulewarden` (`entry: rulewarden hook git pre-commit`, `language: python`, `pass_filenames: false`, `always_run: true`) and `rulewarden-commit-msg` (`stages: [commit-msg]`), as in `docs/integrations.md` |
