Implement `scripts/git-stats.sh [--since DATE] [REPO]` (`REPO` defaults to the current directory).

- Print one line per author of the commits on the current branch: `<count> <author name>`, sorted by count descending, then by name ascending (byte order). Author names may contain spaces and non-ASCII characters.
- Then print `total: <number of commits>`.
- `--since DATE` limits the count to commits after `DATE` (passed to `git log --since`).
- A repository with no commits prints only `total: 0` and exits 0.
- If `REPO` is not a git repository, print an error to stderr and exit 1. An unknown option prints usage to stderr and exits 2.

Add tests for the new behaviour in a new test file (pytest is used to run the script). Run the test suite with `python -m pytest -q`.
