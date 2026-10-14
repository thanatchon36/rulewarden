Implement `scripts/backup.sh SRC_DIR DEST_DIR [KEEP]`.

- Create `DEST_DIR` if needed, then write a gzip tarball of the *contents* of `SRC_DIR` (paths inside the archive are relative to `SRC_DIR`, e.g. `./a.txt` or `a.txt`) to `DEST_DIR/backup-<STAMP>.tar.gz`.
- `<STAMP>` is the current local time as `YYYYmmdd-HHMMSS`, or the value of the environment variable `BACKUP_NOW` if it is set (tests use this).
- After creating the archive, keep only the newest `KEEP` files matching `backup-*.tar.gz` in `DEST_DIR` (newest = greatest name) and delete the others. `KEEP` defaults to 5. Never delete other files in `DEST_DIR`.
- Print the path of the created archive on stdout.
- Errors: fewer than two arguments, or `KEEP` that is not a positive integer: print a usage message to stderr and exit 2. `SRC_DIR` not a directory: print an error to stderr and exit 1.

Add tests for the new behaviour in a new test file (pytest is used to run the script). Run the test suite with `python -m pytest -q`.
