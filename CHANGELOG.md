# Changelog

All notable changes to this project are documented here. The format follows Keep a Changelog, and the project uses
semantic versioning.

## [Unreleased]

### Added
- Zenodo archive: DOI badge in the README and on the docs home page; the concept DOI
  10.5281/zenodo.23368991 in `CITATION.cff`, the BibTeX entry, the paper's appendix and the web reader.

### Changed
- Paper figures redrawn at text width: percentage axes, labelled deterministic shares, an all-files row, line counts,
  categories ordered by size and split by decidability, and a palette that survives greyscale printing.

## [0.1.1] — 2026-10-14

### Added
- Documentation site (`docs/mkdocs.yml`, `make docs`) with a generated CLI reference and rule catalogue.
- The paper as a PDF (`paper/paper.pdf`) and a web reader (`docs/pages/paper/`), both built from `paper/paper.md`
  by `make paper`.
- `CITATION.cff` and `CONTRIBUTING.md`; README rewritten, with its findings table generated from the result files.

### Changed
- `rulewarden init` names the instruction-file rules that the vendored packs already enforce, instead of
  reporting them as compiled with no file written.
- README links are absolute, so they work on PyPI; `docs/integrations.md` pins the published version.
- Paper: prose revised throughout, abstract rewritten and a principal-findings summary added; every
  number is still a placeholder filled from the result files. Authorship note updated.

## [0.1.0] — 2026-10-14

### Added
- Deterministic rule engine: YAML schema with severity (advisory/required/critical) and decidability
  (deterministic/heuristic/undecidable) tiers; engines `regex` (ReDoS-screened), `glob`, `ast`, `jq`, `shell`
  (opt-in, sandboxed) and `python` plugins; bounded execution with a forked watchdog; fail-closed on engine errors
  for blocking rules.
- `rules.lock`: SHA-256 of rule files and protected paths, written only by a human `rulewarden lock` and only when
  every fixture passes.
- Alarm-managed reports (severity first, deduplicated, capped, one `Fix:` per finding) and canonical JSON.
- Deviations with approvers and expiry; agent-authored deviations of blocking rules are critical findings.
- Hash-chained audit log, `report` (including `--framework nist-ai-rmf`) and `stats`.
- Adapters: Claude Code (PreToolUse, PostToolUse, Stop, SessionStart), git hooks (pre-commit, commit-msg,
  pre-push), pre-commit framework, CI with GitHub annotations, Codex, Gemini CLI, OpenCode.
- `compile`: template-based conversion of instruction files, with a report of uncompilable lines.
- `init` (installs agent hooks only together with a lock), `doctor` (wiring, lock, audit chain, determinism).
- Seven starter packs, 26 rules, 120 fixtures.

### Changed
- The Claude Code Stop hook is a warning gate: it blocks only on findings the agent introduced and may fix, and never
  blocks twice in a row (ADR-011).
- Locked rule files are exempt from content rules, and synthetic targets such as `:commit-msg` need explicit
  selection (ADR-012).

### Fixed
- Files that git treats as binary (a NUL byte, UTF-16, UTF-32) were skipped by content rules, so a credential could pass the
  secrets rule. Binary content is now scanned as extracted text by regex rules (ADR-016).
- A bare `check --diff` touching a protected file was exempted when the disk still matched the lock (ADR-016).
- The jq engine refuses a `jq` binary that resolves inside the repository.
- PreToolUse evaluated path-status rules against the file on disk instead of the session baseline, so editing a test
  file the agent had created in the same session was denied as "existing test modified" (benchmark amendment A1).
  The benchmark ran with the defect, which was fixed after the last run.

### Known issues
- The total time budget bounds evaluation, not diff reading; very large diffs can exceed it (they still block).
- PRT-002's protected-path pattern also matches nested directories named `rules/` (NEEDS_HUMAN H6).
- Command rules match command text, so a heredoc that quotes a protected command is denied (ADR-013).
