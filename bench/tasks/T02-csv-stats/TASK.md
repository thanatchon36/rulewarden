Implement `column_stats(path, column)` in `src/csvstats/stats.py`.

- `path` is a CSV file with a header row (UTF-8, comma-separated, may use quoted fields).
- Return a dict with keys `count`, `mean`, `median`, `min`, `max` and `stdev` for the numeric values in `column`. `stdev` is the sample standard deviation, or `0.0` when there is one value.
- Ignore empty cells (after stripping whitespace). `count` is the number of non-empty cells.
- Raise `KeyError` if the column does not exist.
- Raise `ValueError` naming the 1-based data row number if a non-empty cell is not a number.
- Raise `ValueError` if the column has no non-empty cells.
- Values are floats; `count` is an int.

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
