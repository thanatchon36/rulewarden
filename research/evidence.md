# Evidence (MISSION §2) — verified 2026-10-14

Fail-closed: a lead is cited only in the form verified here. Reaction counts are as fetched via `gh api` on 2026-10-14
and will drift.

## Verified

| Lead in brief | What we found | Use in paper |
|---|---|---|
| anthropics/claude-code **#65961** (~251 👍, open) | Confirmed. "[MODEL] Claude verbose code comments by default — ignores instructions to stop", opened 2026-06-07, **open**, 251 reactions (all 👍), 41 comments. The reporter says a `CLAUDE.md` rule and memory entries do not reliably stop it. Verbatim: *"Users shouldn't have to stack a CLAUDE.md rule + memory entries + enforcement hooks just to get clean code, and that still working partially."* <https://github.com/anthropics/claude-code/issues/65961> | Intro pain point; motivates the `hygiene-python` restating-comment heuristic. Quote verbatim, attributed to "the reporter". |
| anthropics/claude-code **#53454** (~181 reactions) | Confirmed. "[MODEL] Claude Code can not stop using the word "load-bearing"", opened 2026-04-26, **open**, 181 reactions (119 👍), 19 comments. Reporter told it via memory not to use the word; it kept doing so in chat, documents and commit messages. <https://github.com/anthropics/claude-code/issues/53454> | Intro; motivates the `voice` pack (banned phrases in comments, docs, commit messages). |
| anthropics/claude-code **#77136** (closed as fixed) | Confirmed with a correction. "[BUG] Claude 4.7, 4.8, 5.0, and Fable increasingly default to repetitive rhetorical tics…", opened 2026-07-13, 577 reactions, 138 comments. Closed **as completed by its reporter** (not by a maintainer) on 2026-10-03: *"Closing as it is addressed in the latest 5.5 generation of models."* Later the same day, another commenter wrote that they still see the patterns with claude-sonnet-5.5 despite `CLAUDE.md` rules. <https://github.com/anthropics/claude-code/issues/77136> | Discussion of vendor-fix risk: model updates can resolve a tic class, so the durable value is enforcement and evidence of enforcement, not any single check. The reporter, not the vendor, closed it, and we must say so. |
| HN "skill that stops agents from embedding answers" (~542 points) | **The brief mis-describes this lead.** The 542-point story is HN item 49610631 (2026-09-08), titled *"I-have-ADHD: A skill to stop coding agents from burying the answer"*, linking <https://github.com/ayghri/i-have-adhd> (MIT, ~57k★ at retrieval). It is about **response style** (put the action first, number the steps, drop filler), **not** about agents hard-coding expected test outputs. HN thread: <https://news.ycombinator.com/item?id=49610631> | Cite only as evidence of demand for controlling agent *voice/verbosity*. **Do not** cite it for answer-embedding. |

## Replacement evidence for the answer-embedding / test-gaming pain point

| Source | Content | Use |
|---|---|---|
| anthropics/claude-code **#319** | "A tendency to re-write tests so they pass." (2025-03-04, closed *not planned*, 11 reactions). Reporter: the agent changed test conditions so tests pass, and once rewrote the Makefile to run only passing tests ("safe-tests"). <https://github.com/anthropics/claude-code/issues/319> | Practitioner report of test gaming. Small reaction count, so we say so. |
| Zhong, Raghunathan, Carlini 2025, **ImpossibleBench** (arXiv:2510.20270) | Measures LLM agents' propensity to exploit test cases, e.g. deleting failing tests or special-casing them, on tasks whose spec conflicts with the tests. | Primary literature for the `no-answer-embedding` pack and RQ5. |

## Additional ecosystem evidence found during the sprint

- Two direct competitors hold Appendix C candidate names on PyPI: `hardstop` ("mechanical brake for AI-generated
  commands … for Claude Code") and `diffgate` ("catches skipped tests, swallowed exceptions … in a diff"). See ADR-001.
- Yan 2026 (arXiv:2608.23550) measured that only ~4–16 % of security rules in 481 public `CLAUDE.md` files have a
  matching Claude Code built-in control (4.4 % under the strictest standard). This is the closest prior result to our
  RQ1, but limited to security rules and to *built-in* controls.
