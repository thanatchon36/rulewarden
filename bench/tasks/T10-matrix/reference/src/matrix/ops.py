from fractions import Fraction

Matrix = list[list[float]]


def _check(m: Matrix) -> tuple[int, int]:
    if not m or not m[0] or any(len(r) != len(m[0]) for r in m):
        raise ValueError("matrix must be non-empty and rectangular")
    return len(m), len(m[0])


def transpose(m: Matrix) -> Matrix:
    _check(m)
    return [list(col) for col in zip(*m, strict=True)]


def matmul(a: Matrix, b: Matrix) -> Matrix:
    _, k = _check(a)
    k2, _ = _check(b)
    if k != k2:
        raise ValueError(f"shape mismatch: {k} columns vs {k2} rows")
    cols = transpose(b)
    return [[sum(x * y for x, y in zip(row, col, strict=True)) for col in cols] for row in a]


def identity(n: int) -> Matrix:
    if n < 1:
        raise ValueError("n must be at least 1")
    return [[1 if i == j else 0 for j in range(n)] for i in range(n)]


def determinant(m: Matrix) -> float:
    """Determinant by Gaussian elimination; exact for int and Fraction entries."""
    rows, cols = _check(m)
    if rows != cols:
        raise ValueError("determinant needs a square matrix")
    exact = all(isinstance(x, (int, Fraction)) for r in m for x in r)
    a = [[Fraction(x) if exact else x for x in r] for r in m]
    det = Fraction(1) if exact else 1.0
    for i in range(rows):
        pivot = next((r for r in range(i, rows) if a[r][i] != 0), None)
        if pivot is None:
            return 0
        if pivot != i:
            a[i], a[pivot] = a[pivot], a[i]
            det = -det
        det *= a[i][i]
        for r in range(i + 1, rows):
            f = a[r][i] / a[i][i]
            a[r] = [x - f * y for x, y in zip(a[r], a[i], strict=True)]
    if exact and all(isinstance(x, int) for r in m for x in r):
        return int(det)
    return det
