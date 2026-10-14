#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: summarize.sh FILE" >&2
  exit 2
fi
file=$1
if [[ ! -f $file ]]; then
  echo "summarize.sh: no such file: $file" >&2
  exit 1
fi
if ! jq -e 'type == "array"' "$file" >/dev/null 2>&1; then
  echo "summarize.sh: not a JSON array: $file" >&2
  exit 1
fi

jq -r '
  [.[] | select(.status == "paid")] as $paid
  | ($paid | group_by(.customer) | map({c: .[0].customer, t: (map(.total) | add)})
     | sort_by(-.t, .c) | (.[0].c // "-")) as $top
  | "orders: \(length)",
    "paid: \($paid | length)",
    "revenue: \(($paid | map(.total) | add // 0) * 100 | round / 100 | tostring
                 | if test("\\.") then (split(".") | .[0] + "." + (.[1] + "00")[0:2]) else . + ".00" end)",
    "top: \($top)"
' "$file"
