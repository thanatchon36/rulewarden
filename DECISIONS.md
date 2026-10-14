# DECISIONS.md

Architecture/mission decision records. Format: context · options · choice · reversibility.
Newest at the bottom. A fresh session should read all of them before changing direction.

---

## ADR-001 — Project name: `rulewarden` (2026-10-14)

**Context.** Appendix C gives a deterministic procedure over `abide, hardstop, failclosed, diffgate, lockout, rulebag`.
The owner created the project directory as `rulewarden` before kickoff.

**Evidence (checked 2026-10-14).**

| Candidate | PyPI `/pypi/<n>/json` | GitHub repos named so (>100★, agent/devtools) | Web: AI-agent-policy product |
|---|---|---|---|
| abide | 200 (taken: "intelligent information bagging") | – | – |
| hardstop | 200 (taken: "mechanical brake for AI-generated commands … for Claude Code") — **direct competitor** | – | – |
| failclosed | 200 (taken: default-deny ASGI middleware) | – | – |
| diffgate | 200 (taken: "catches skipped tests, swallowed exceptions … in a diff") — **adjacent competitor** | – | – |
| lockout | 200 (taken: sparse NN regularisation) | – | – |
| rulebag | 404 | none found (`gh search repos rulebag`) | none found |
| rulewarden | 404 | none found (`gh search repos rulewarden`) | none found |

**Options.** (a) `rulebag` — first passing Appendix C candidate. (b) `rulewarden` — the directory name the owner chose,
also passes all three checks.

**Choice.** `rulewarden`. The owner's directory name is a later and more specific signal than the candidate list;
containment (§9.1) forbids renaming the parent directory; package = repo = CLI = directory keeps the layout of §12 exact;
"warden" also states the product's role (a monitor with authority), whereas "bag" does not.

**Reversibility.** High until the GitHub repo is public and PyPI is published (neither is done by the agent). A rename is a
search-and-replace of `rulewarden` plus moving `src/rulewarden`. Listed in `NEEDS_HUMAN.md` for confirmation.

## ADR-002 — Python pinned to 3.12 locally, support ≥3.11 (2026-10-14)

`uv python pin 3.12`; CI tests 3.11 and 3.12 on Linux and macOS. Reversible: edit `.python-version`.

## ADR-003 — Paper toolchain: Markdown + pandoc → Typst PDF (2026-10-14)

**Context.** §7 prefers LaTeX/latexmk; no TeX installation is present (`latexmk`, `pdflatex`, `xelatex` missing). `pandoc 3.8`
and `typst` are installed. **Options.** Install MacTeX (~5 GB, outside project dir, not reversible-cheap) · pandoc+typst.
**Choice.** pandoc + `--pdf-engine=typst`, explicitly permitted by §7 ("if TeX is unavailable, Markdown + pandoc with the
same content"). `paper/main.md` is the source; `make paper` builds `paper/build/main.pdf`. **Reversibility.** High: pandoc
can emit `main.tex` from the same source later.

## ADR-004 — GitHub repo created **private**; going public is a human action (2026-10-14)

**Context.** §0.3 says "public repo … create with gh if authenticated". The kickoff prompt also says anything irreversible or
with legal exposure goes to `NEEDS_HUMAN.md`. Publishing is irreversible (content is cached/indexed), and the repo will
contain third-party corpus excerpts (license-filtered) and recorded agent transcripts, which carry some legal exposure.
**Options.** Public now · private now, public at the end by the agent · private, human flips visibility.
**Choice.** Create `thanatchon36/rulewarden` **private**, push every checkpoint, put "review and flip to public" in
`NEEDS_HUMAN.md`. **Reversibility.** Full — `gh repo edit --visibility public` is one command for the human.

## ADR-005 — Bootstrapping the protected set (2026-10-14)

**Context.** Appendix A forbids the agent to touch `rules/`, `rules.lock`, `.claude/`, `.pre-commit-config.yaml`,
`.github/workflows/`, `.rulewarden/`. Someone must create them first, and the mission makes the agent the only engineer.
**Choice.** All protected files are created in a single **bootstrap window** (Phases 0–2, before enforcement is switched
on), and designed so later work never needs to change them: CI, pre-commit and Claude Code hooks only call `make` targets
and `rulewarden hook …` entry points, so behaviour evolves through unprotected files (`Makefile`, `src/`). The bootstrap
lock is recorded as "agent acting as bootstrap human" in the audit log. After enforcement is on, any change the agent
wants in the protected set is written as a proposal under `proposals/` and listed in `NEEDS_HUMAN.md`; the agent does not
approve its own protected changes. **Reversibility.** High; the human can re-lock at any time.

## ADR-006 — Starter packs ship inside the package; the repo vendors copies (2026-10-14)

**Context.** §12 shows `rules/packs/`. Packs must ship in the wheel for `rulewarden init`, and `rules/` is protected, so
developing packs there would require human approval for every edit.
**Choice.** Canonical packs live in `src/rulewarden/packs/*.yaml` (package data). `rulewarden init` vendors selected packs
into a project's `rules/packs/`. This repo's `rules/packs/` is such a vendored copy, locked by `rules.lock`; pack edits in
`src/` do not silently change the enforced rule set (a human re-vendors and re-locks). **Reversibility.** High.
