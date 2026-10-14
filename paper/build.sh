#!/usr/bin/env bash
# Build the paper: verify references (unless --no-network), recompute the numbers, render
# paper/paper.md and the README findings (fails on an unresolved number or unverified citation),
# then the PDF and web reader if pandoc exists. paper/build/ feeds the CI artifact.
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
"${run[@]}" python paper/findings.py
mkdir -p paper/build
cp paper/paper.md paper/build/paper.md

if command -v pandoc >/dev/null 2>&1; then
  "${run[@]}" --group paper python paper/build_paper.py
else
  echo "pandoc not found: rendered paper/paper.md only (PDF and web reader not rebuilt)"
fi
