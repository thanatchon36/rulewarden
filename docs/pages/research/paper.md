# The paper

*rulewarden: Deterministic Runtime Assurance for AI Coding Agents. Borrowing Safety-Critical Systems
Engineering to Enforce Agent Instruction Files.*

| | |
|---|---|
| **Read it on the web** | [paper/](../paper/index.html): one reading column, with the abstract, the pre-registered results, figures and references |
| **Download the PDF** | [paper.pdf](https://github.com/thanatchon36/rulewarden/raw/main/paper/paper.pdf), typeset with Typst |
| Markdown source | [`paper/main.md`](https://github.com/thanatchon36/rulewarden/blob/main/paper/main.md), rendered to [`paper/paper.md`](https://github.com/thanatchon36/rulewarden/blob/main/paper/paper.md) |
| Every number in it | filled from generated results (`corpus/data/summary.json`, `bench/results/summary.json`, `bench/results/rq3.json`, `paper/data/dogfood_audit.json`); an unresolved number or an unverified citation fails the build |

## Research questions

- **RQ1 (corpus).** What fraction of rules in real-world agent instruction files is deterministically
  checkable, heuristic, or undecidable, and which categories dominate? See [Corpus study](corpus.md).
- **RQ2 (effectiveness).** Does deterministic hook enforcement reduce rule violations in the final diff
  compared with rules in the instruction file alone, and at what cost? See [Benchmark](benchmark.md).
- **RQ3 (safety properties).** Does the tool hold its determinism and fail-closed guarantees under adversarial
  inputs, and how fast is it?
- **RQ4 (alarm management).** Does severity-first, capped reporting improve self-correction over a flat list?
- **RQ5 (independence).** Under an adversarial prompt, does the agent try to edit its own checks, and are those
  attempts blocked?

## Reproduce

```bash
make corpus     # RQ1 from corpus/data/
make replay     # RQ2–RQ5 from bench/recorded/ — no API key needed
make paper      # verifies references, renders paper/paper.md, the PDF and the web reader
```

The manuscript was drafted by Claude Opus 5.5 and revised by Claude Fable 5.1 (both Anthropic) from the author's
design, data and recordings, under
the constraint that every number is generated and every refuted expectation and tool defect is reported. The
author is responsible for its content.
