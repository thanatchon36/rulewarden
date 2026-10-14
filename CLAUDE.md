# Rules for agents working in this repository
Scope
- Edit only inside this repository. Never touch rules/, rules.lock, .claude/, .pre-commit-config.yaml,
  .github/workflows/ or .rulewarden/ — a human changes those.
- Never run git with --no-verify, --force, or history-rewriting commands. Never rm -rf outside the repo.
- Do not add runtime dependencies without recording the reason in DECISIONS.md.
Code
- Python ≥ 3.11, ruff-formatted, mypy --strict clean. No bare except. No print() in src/ (use logging).
- No comments that restate the code. Docstrings ≤ 8 lines. No TODO without an issue reference.
- Use jq for JSON in shell scripts; no python -c one-liners in *.sh.
Tests and evidence
- Never modify a test to make it pass; never hard-code expected outputs; never fabricate fixtures, results or references.
- Every rule you add ships with at least one passing and one failing fixture.
Voice
- No filler phrases in comments, docs or commit messages (configured list in rules/packs/voice.yaml).
Process
- Commit at every checkpoint with Conventional Commits. Keep STATUS.md and DECISIONS.md current.
