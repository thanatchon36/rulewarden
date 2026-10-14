#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: render.sh TEMPLATE VALUES" >&2
  exit 2
fi
template=$1
values=$2
for f in "$template" "$values"; do
  if [[ ! -f $f ]]; then
    echo "render.sh: no such file: $f" >&2
    exit 1
  fi
done
if ! jq -e 'type == "object"' "$values" >/dev/null 2>&1; then
  echo "render.sh: values must be a JSON object: $values" >&2
  exit 1
fi

pattern='\{\{(?<k>[A-Za-z0-9_.]+)\}\}'
bad=$(jq -Rsr --slurpfile v "$values" --arg re "$pattern" '
  [scan($re) | .[0]] | reduce .[] as $k ([]; if index([$k]) then . else . + [$k] end)
  | map(select(. as $k | ($v[0] | getpath($k | split("."))? // null) as $x
      | ($x == null or ($x | type) == "object" or ($x | type) == "array")))
  | .[]' "$template")
if [[ -n $bad ]]; then
  while IFS= read -r key; do
    echo "render.sh: bad key $key" >&2
  done <<<"$bad"
  exit 1
fi

jq -Rsj --slurpfile v "$values" --arg re "$pattern" '
  gsub($re; .k as $k | ($v[0] | getpath($k | split("."))) as $x
    | if ($x | type) == "string" then $x else ($x | tojson) end)
' "$template"
