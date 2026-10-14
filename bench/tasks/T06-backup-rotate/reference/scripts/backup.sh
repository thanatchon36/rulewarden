#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: backup.sh SRC_DIR DEST_DIR [KEEP]" >&2
  exit 2
}

[[ $# -ge 2 ]] || usage
src=$1
dest=$2
keep=${3:-5}
[[ $keep =~ ^[1-9][0-9]*$ ]] || usage
if [[ ! -d $src ]]; then
  echo "backup.sh: not a directory: $src" >&2
  exit 1
fi

mkdir -p "$dest"
stamp=${BACKUP_NOW:-$(date +%Y%m%d-%H%M%S)}
archive="$dest/backup-$stamp.tar.gz"
tar -czf "$archive" -C "$src" .

backups=()
while IFS= read -r name; do
  backups+=("$name")
done < <(find "$dest" -maxdepth 1 -type f -name 'backup-*.tar.gz' -exec basename {} \; | LC_ALL=C sort -r)

for ((i = keep; i < ${#backups[@]}; i++)); do
  rm -f -- "$dest/${backups[$i]}"
done

echo "$archive"
