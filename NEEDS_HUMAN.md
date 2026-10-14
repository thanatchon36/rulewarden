# NEEDS_HUMAN.md

Actions the agent must not take on its own (irreversible, costs money, or legal exposure). Each item says what, why,
and the exact command or file to review. The agent keeps working on everything else.

| # | Item | Why it needs a human | How |
|---|---|---|---|
| H1 | Confirm the name `rulewarden` (ADR-001) | Naming is sticky once public/published | Rename = search/replace before going public |
| H2 | Flip GitHub repo to public (ADR-004) | Publishing is irreversible; corpus excerpts and transcripts carry licence exposure | Review `corpus/data/`, `bench/recorded/`, then `gh repo edit thanatchon36/rulewarden --visibility public --accept-visibility-change-consequences` |
| H3 | Publish to PyPI | §0.3: the human releases | Configure trusted publisher on PyPI for `.github/workflows/release.yml`, then push tag `v0.1.0` |
| H4 | Push local commits to `origin` | `git push` is denied by this session's permission settings (the first push during `gh repo create` went through; later pushes were refused 2026-10-14). The agent commits locally and does not try to get around the denial | `git push origin main` (and `git push --tags` if a tag exists) |
