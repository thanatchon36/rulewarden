# Corpus study (RQ1)

**Question.** What fraction of rules in real-world agent instruction files is deterministically checkable,
heuristic, or undecidable, and which rule categories dominate?

## Collection plan (fixed before collection)

- **Source**: GitHub code search REST API (`gh api search/code`), authenticated, 10 requests/min limit honoured.
- **File types (strata)** and queries, one stratum each, **60 files per stratum**, total cap `CORPUS_MAX_FILES=300`:

  | Stratum | Query |
  |---|---|
  | `CLAUDE.md` | `filename:CLAUDE.md` |
  | `AGENTS.md` | `filename:AGENTS.md` |
  | `.cursorrules` | `filename:.cursorrules` |
  | `GEMINI.md` | `filename:GEMINI.md` |
  | `.windsurfrules` | `filename:.windsurfrules` |

- **Order and selection**: results are taken in API order, page by page (100 per page), skipping (a) forks,
  (b) a second file from a repo already sampled in any stratum, (c) files > 200 KB, and (d) repos whose licence is not
  OSI-approved (see licensing below), until the stratum reaches 60 or results run out. API ordering is not random.
  This is a **convenience sample** and the paper says so.
- **Recorded per file**: stratum, repo full name, path, file blob SHA, repo default-branch commit SHA at collection
  time, SPDX licence id, stars, collection timestamp. → `corpus/data/files.csv`.

## Licensing (fail-closed)

- Verbatim rule lines are stored **only** for repos whose SPDX licence is on the OSI-approved allowlist in
  `corpus/collect.py`. Other repos are skipped at collection time, so their text is never stored.
- Every stored line is passed through the rulewarden `secrets` pack. A line that matches is replaced by its SHA-256 and
  labels only. E-mail addresses and `@handles` are masked.

## Extraction

`corpus/extract.py`: a line (or bullet item) is *rule-like* if, after stripping markdown, it contains an imperative or
modal cue from a fixed lexicon (`always, never, do not, don't, must, should, prefer, avoid, use, only, ensure, make
sure, no …`). Code blocks are excluded. Output: `corpus/data/rules.csv` (file id, line number, text or hash).

## Labelling

1. **Deterministic rubric** (`corpus/label.py`, primary labels): ordered regex rules map each line to a **category**
   (style, tooling, scope, process, testing, security, voice, other) and a **decidability** tier (P3):
   *deterministic* (checkable on a diff/command with a regex/glob/AST/path rule, e.g. "never commit .env",
   "use pnpm not npm"), *heuristic* (checkable approximately, e.g. "keep functions short", "avoid redundant
   comments"), *undecidable* (needs intent or semantics, e.g. "write clean code", "think before acting").
   The rubric also tags whether a line matches a shipped **compile template** (i.e. `rulewarden compile` would
   produce a rule for it).
2. **Model-assisted labels** (secondary): the same lines are labelled by a model with a fixed prompt
   (`corpus/prompts/label_v1.txt`) in **two independent passes**. The CLI exposes no temperature control, so we do not
   claim temperature 0. Cohen's κ is reported for pass 1 vs pass 2 and for rubric vs model (majority/first pass).
   All labels are published in `corpus/data/labels.csv` / `.parquet`.
3. The paper states that labels are rubric-based and model-assisted, and reports both.

## Outputs

`corpus/data/files.csv`, `rules.csv`, `labels.csv`, `labels.parquet`, `summary.json`; figures in `paper/figures/`.
Rebuild the analysis offline: `make corpus` (needs only `corpus/data/`).
