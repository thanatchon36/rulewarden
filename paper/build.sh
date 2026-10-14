#!/usr/bin/env bash
# Build the paper from scripts: verify references (unless --no-network), recompute corpus and
# benchmark numbers, render placeholders (fails on any unresolved number or unverified citation),
# then convert to HTML with pandoc when it is installed.
set -euo pipefail

cd "$(dirname "$0")/.."
network=1
if [[ ${1:-} == "--no-network" ]]; then
  network=0
fi
run=(uv run --frozen)

if [[ $network -eq 1 ]]; then
  "${run[@]}" python paper/verify_refs.py
fi
"${run[@]}" --group research python corpus/analyse.py
"${run[@]}" --group research python bench/replay.py --check
"${run[@]}" python paper/render.py

if command -v pandoc >/dev/null 2>&1; then
  pandoc paper/build/main.md \
    --from markdown --citeproc --bibliography paper/refs.verified.bib \
    --resource-path paper --standalone --embed-resources \
    --metadata link-citations=true --toc \
    -o paper/build/paper.html
  echo "built paper/build/paper.html"
else
  echo "pandoc not found: rendered markdown only (paper/build/main.md)"
fi
