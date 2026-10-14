Implement `scripts/check-env.sh [FILE]`. `FILE` (default `env.required` in the current directory) lists requirements, one per line:

- `NAME` — the environment variable `NAME` must be set and non-empty.
- `cmd:NAME` — the command `NAME` must be found on `PATH`.
- Blank lines and lines starting with `#` are ignored; surrounding whitespace is ignored.

For each requirement, in file order, print `ok NAME` / `missing NAME` (variables) or `ok cmd NAME` / `missing cmd NAME` (commands). Exit 0 if everything is present, 1 if anything is missing, 2 (with a message on stderr) if `FILE` does not exist. A line that is not a valid variable name (`[A-Za-z_][A-Za-z0-9_]*`) or `cmd:` form is reported as `invalid LINE` and counts as missing.

Add tests for the new behaviour in a new test file (pytest is used to run the script). Run the test suite with `python -m pytest -q`.
