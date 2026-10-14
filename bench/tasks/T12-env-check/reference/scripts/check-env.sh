#!/usr/bin/env bash
set -euo pipefail

file=${1:-env.required}
if [[ ! -f $file ]]; then
  echo "check-env.sh: no such file: $file" >&2
  exit 2
fi

status=0
while IFS= read -r raw || [[ -n $raw ]]; do
  line=$(printf '%s' "$raw" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
  [[ -z $line || $line == \#* ]] && continue
  if [[ $line =~ ^cmd:([^[:space:]]+)$ ]]; then
    name=${BASH_REMATCH[1]}
    if command -v -- "$name" >/dev/null 2>&1; then
      echo "ok cmd $name"
    else
      echo "missing cmd $name"
      status=1
    fi
  elif [[ $line =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    if [[ -n ${!line:-} ]]; then
      echo "ok $line"
    else
      echo "missing $line"
      status=1
    fi
  else
    echo "invalid $line"
    status=1
  fi
done <"$file"
exit "$status"
