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
modal cue from a fixed lexicon. The lexicon is `_CUE_RE` in `src/rulewarden/compile/extract.py`, the same extractor
`rulewarden compile` uses, so the study measures what the tool sees. Code blocks, headings, tables and HTML comments
are excluded. The extractor is deliberately broad, so it also catches descriptive lines (for example "Tests use
.mjs"); the model labels flag those with `is_rule` (below). Output: `corpus/data/rules.csv` (file id, line number,
text or hash).

## Labelling

1. **Deterministic rubric** (`corpus/label.py`, primary labels): ordered regex rules map each line to a **category**
   (style, tooling, scope, process, testing, security, voice, other; first match wins) and a **decidability** tier
   (P3), judged against a checker that sees only the diff and the commands:
   - *deterministic*: a concrete token (code span, path, file extension, tool name, number with a unit, named
     syntax such as `console.log` or camelCase) together with a prohibition ("never", "do not", "avoid", a leading
     "No"), or together with a prescription (a modal, or an imperative such as "Use"/"Keep" at the start) that is
     not an obligation to act;
   - obligations to act ("Run …", "Check …", "Ask …") are *undecidable* from a diff unless phrased as a
     prohibition, because a diff cannot show that something was done;
   - *heuristic*: an approximate-quality cue (short, concise, duplication, nesting, redundant, …);
   - *undecidable*: everything else (intent, judgement, vague quality words).
   The rubric also tags whether a shipped **compile template** matches the line (`compilable`, i.e.
   `rulewarden compile` would produce a rule for it). `tests/test_corpus_rubric.py` pins the documented examples.
   The rubric was revised once, before any model labels existed: a 40-line sample of the first 120 files showed
   descriptive lines ("Tests use .mjs extension") labelled deterministic because of a mid-sentence "use".
2. **Model-assisted labels** (secondary): the same lines are labelled by `claude -p --model haiku` (Haiku 5.5),
   with no tools, no settings files, no MCP servers, in an empty directory, using the fixed prompt
   `corpus/prompts/label_v1.txt`, in batches of 80 lines, in **two independent passes** (pass 2 sees each batch in
   reverse order). The model also returns `is_rule` (does the line instruct the agent, or only describe the
   project?). The CLI exposes no temperature control, so we do not claim temperature 0. Cohen's κ is reported for
   pass 1 vs pass 2 and for rubric vs pass 1. Raw responses are kept in `corpus/data/model_raw/`.
3. Shares are reported for all extracted lines and for the *rules-only* subset (both passes say `is_rule`), with
   95% bootstrap CIs that resample files (2,000 resamples, fixed seed), because lines are nested in files.
4. The paper states that labels are rubric-based and model-assisted, and reports both.

## Outputs

`corpus/data/files.csv`, `rules.csv`, `labels.csv`, `labels.parquet`, `summary.json`; figures in `paper/figures/`.
Rebuild the analysis offline: `make corpus` (needs only `corpus/data/`).
