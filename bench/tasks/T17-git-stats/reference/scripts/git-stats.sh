#!/usr/bin/env bash
set -euo pipefail

since=()
repo=.
while [[ $# -gt 0 ]]; do
  case $1 in
    --since)
      [[ $# -ge 2 ]] || { echo "usage: git-stats.sh [--since DATE] [REPO]" >&2; exit 2; }
      since=(--since "$2")
      shift 2
      ;;
    -*)
      echo "usage: git-stats.sh [--since DATE] [REPO]" >&2
      exit 2
      ;;
    *)
      repo=$1
      shift
      ;;
  esac
done

if ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
  echo "git-stats.sh: not a git repository: $repo" >&2
  exit 1
fi
if ! git -C "$repo" rev-parse --verify -q HEAD >/dev/null; then
  echo "total: 0"
  exit 0
fi

authors=$(git -C "$repo" log ${since[@]+"${since[@]}"} --format='%an')
if [[ -n $authors ]]; then
  tab=$(printf '\t')
  printf '%s\n' "$authors" | LC_ALL=C sort | uniq -c \
    | sed -E "s/^ *([0-9]+) (.*)\$/\\1${tab}\\2/" \
    | LC_ALL=C sort -t "$tab" -k1,1nr -k2,2 \
    | tr '\t' ' '
  total=$(printf '%s\n' "$authors" | wc -l | tr -d ' ')
else
  total=0
fi
echo "total: $total"
