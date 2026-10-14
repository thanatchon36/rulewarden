Implement matrix helpers on lists of lists in `src/matrix/ops.py`:

- `transpose(m)`, `matmul(a, b)`, `identity(n)` and `determinant(m)`.
- A matrix is a non-empty list of non-empty rows of equal length containing ints, floats or `fractions.Fraction`. Raise `ValueError` for ragged or empty matrices, for `matmul` shape mismatches, for a non-square `determinant` argument, and for `identity(n)` with `n < 1`.
- `determinant` must be exact for int and `Fraction` input (return an `int` for int matrices, a `Fraction` for `Fraction` matrices) and work for any size up to at least 8×8. Float input may return a float.
- Functions must not modify their arguments.

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
