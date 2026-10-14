Implement `scripts/cleanup.sh [-n] DIR DAYS [PATTERN]`.

- Delete regular files under `DIR` (recursively) whose modification time is more than `DAYS` days ago and whose name matches the shell glob `PATTERN` (default `*`). `DAYS` is a non-negative integer.
- Never delete directories, and never follow symbolic links (a symlink itself is not deleted either).
- Print each deleted path (as found under `DIR`) on its own line, sorted. With `-n` (dry run), print the paths that would be deleted and delete nothing.
- Refuse to run (message on stderr, exit 1) if `DIR` is empty, `/`, or the user's home directory, or is not a directory.
- Bad usage (wrong number of arguments, `DAYS` not a non-negative integer): message on stderr, exit 2.

Add tests for the new behaviour in a new test file (pytest is used to run the script). Run the test suite with `python -m pytest -q`.
