SHELL := /bin/bash
.DEFAULT_GOAL := check
UV ?= uv
RUN := $(UV) run --frozen

.PHONY: check ci ci-gate paper-ci lint fmt types test cov test-rules determinism selfcheck paper docs docs-serve replay corpus bench-report refs clean

check: lint types cov test-rules determinism selfcheck

ci: check replay docs

# CI entry points (the workflow files only call these targets; see ADR-005).
ci-gate:
	$(RUN) rulewarden hook ci $${RULEWARDEN_BASE:-origin/main}

paper-ci:
	bash paper/build.sh --no-network

lint:
	$(RUN) ruff format --check .
	$(RUN) ruff check .

fmt:
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

types:
	$(RUN) mypy

test:
	$(RUN) pytest

cov:
	$(RUN) pytest --cov --cov-report=term

test-rules:
	$(RUN) rulewarden test-rules
	$(RUN) rulewarden test-rules --path src/rulewarden/packs

determinism:
	$(RUN) rulewarden doctor --determinism-only

selfcheck:
	$(RUN) rulewarden check --working-tree --harness make

replay:
	@if [ -f bench/replay.py ]; then $(RUN) --group research python bench/replay.py --check; else echo "replay: not implemented yet"; fi

corpus:
	$(RUN) --group research python corpus/analyse.py

# Rebuild paper/paper.md, paper/paper.pdf and the web reader docs/pages/paper/ (PDF and reader need pandoc).
paper:
	bash paper/build.sh

# Regenerate the reference pages, then build the site into site/ (git-ignored).
docs:
	$(RUN) python docs/gen_reference.py
	$(RUN) --group docs mkdocs build --strict -f docs/mkdocs.yml

docs-serve:
	$(RUN) --group docs mkdocs serve -f docs/mkdocs.yml

refs:
	$(RUN) python paper/verify_refs.py

clean:
	rm -rf dist build site .pytest_cache .mypy_cache .ruff_cache .coverage paper/build
