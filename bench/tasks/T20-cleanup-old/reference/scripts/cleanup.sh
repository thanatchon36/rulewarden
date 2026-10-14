#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: cleanup.sh [-n] DIR DAYS [PATTERN]" >&2
  exit 2
}

dry=0
if [[ ${1:-} == "-n" ]]; then
  dry=1
  shift
fi
[[ $# -eq 2 || $# -eq 3 ]] || usage
dir=$1
days=$2
pattern=${3:-*}
[[ $days =~ ^[0-9]+$ ]] || usage

if [[ -z $dir || $dir == "/" || ! -d $dir ]]; then
  echo "cleanup.sh: refusing to clean '$dir'" >&2
  exit 1
fi
real=$(cd "$dir" && pwd -P)
home=$(cd "${HOME:-/nonexistent}" 2>/dev/null && pwd -P || true)
if [[ $real == "/" || $real == "$home" ]]; then
  echo "cleanup.sh: refusing to clean '$dir'" >&2
  exit 1
fi

matches=()
while IFS= read -r -d '' f; do
  matches+=("$f")
done < <(find "$dir" -type f -name "$pattern" -mtime +"$days" -print0)

if [[ ${#matches[@]} -gt 0 ]]; then
  printf '%s\n' "${matches[@]}" | LC_ALL=C sort
  if [[ $dry -eq 0 ]]; then
    for f in "${matches[@]}"; do
      rm -f -- "$f"
    done
  fi
fi
