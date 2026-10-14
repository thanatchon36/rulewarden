SHELL := /bin/bash
.DEFAULT_GOAL := check
UV ?= uv
RUN := $(UV) run --frozen

.PHONY: check ci lint fmt types test cov test-rules determinism selfcheck paper replay corpus bench-report clean

check: lint types cov test-rules determinism selfcheck

ci: check replay

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
	@if $(RUN) rulewarden --help 2>/dev/null | grep -q test-rules; then $(RUN) rulewarden test-rules; else echo "test-rules: not implemented yet"; fi

determinism:
	@if $(RUN) rulewarden --help 2>/dev/null | grep -q doctor; then $(RUN) rulewarden doctor --determinism-only; else echo "determinism: not implemented yet"; fi

selfcheck:
	@if $(RUN) rulewarden --help 2>/dev/null | grep -q ' check '; then $(RUN) rulewarden check --working-tree; else echo "selfcheck: not implemented yet"; fi

replay:
	@if [ -f bench/replay.py ]; then $(RUN) --group research python bench/replay.py --check; else echo "replay: not implemented yet"; fi

corpus:
	$(RUN) --group research python corpus/analyse.py

paper:
	bash paper/build.sh

clean:
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache .coverage paper/build
