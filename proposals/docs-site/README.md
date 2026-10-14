# Proposal: publish the documentation site (NEEDS_HUMAN H8)

Prepared by the agent; **a human reviews `docs.yml`, installs it and locks**. Workflow files are protected, so the
agent cannot add it, and it does not lock (ADR-018).

The site is `docs/mkdocs.yml` built by `make docs` into `site/`. It contains the user documentation, the generated
CLI reference and rule catalogue, the project records, and the paper as a web reader (`/paper/`) with its PDF
(`/paper/paper.pdf`). The README and `docs/pages/research/paper.md` already link to
`https://thanatchon36.github.io/rulewarden/`.

## Why it waits for H2

A GitHub Pages site is public even when the repository is private. Deploying it would publish the paper, the
benchmark summary and the project records before the licence and path review that H2 asks for. The workflow
therefore builds on every push to `main` (so a broken site shows up in CI) but deploys only when the repository
variable `PAGES_PUBLISH` is `true`, the same gate `release.yml` uses for PyPI.

Verification done by the agent: `make docs` passes (`mkdocs build --strict`), and the workflow YAML parses. The
deploy job has not run.

## Apply (after H2, from the repository root)

```bash
cp proposals/docs-site/docs.yml .github/workflows/docs.yml \
  && uv run --frozen rulewarden test-rules && uv run --frozen rulewarden lock --ci \
  && gh api -X POST repos/thanatchon36/rulewarden/pages -f build_type=workflow \
  && gh variable set PAGES_PUBLISH --body true --repo thanatchon36/rulewarden \
  && git add .github/workflows/docs.yml rules.lock && git commit -m "ci(docs): deploy the documentation site to GitHub Pages"
```

Then push. The first deploy follows the push; the site appears at `https://thanatchon36.github.io/rulewarden/`.

## Roll back

`gh variable set PAGES_PUBLISH --body false --repo thanatchon36/rulewarden` stops deployments; unpublish the site in
Settings → Pages.
