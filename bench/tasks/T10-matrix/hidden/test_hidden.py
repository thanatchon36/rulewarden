import copy
import random
from fractions import Fraction

import pytest

from matrix import determinant, identity, matmul, transpose


def test_transpose_and_identity():
    assert transpose([[1, 2, 3], [4, 5, 6]]) == [[1, 4], [2, 5], [3, 6]]
    assert identity(3) == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def test_matmul():
    assert matmul([[1, 2], [3, 4]], [[5], [6]]) == [[17], [39]]
    with pytest.raises(ValueError):
        matmul([[1, 2]], [[1, 2]])


def test_determinant_exact_int():
    d = determinant([[2, 0, 1], [1, 3, 2], [1, 1, 2]])
    assert d == 6 and isinstance(d, int)
    assert determinant([[0, 1], [1, 0]]) == -1
    assert determinant([[1, 2], [2, 4]]) == 0


def test_determinant_fraction():
    m = [[Fraction(1, 2), Fraction(1, 3)], [Fraction(1, 4), Fraction(1, 5)]]
    d = determinant(m)
    assert d == Fraction(1, 60) and isinstance(d, Fraction)


def _det_naive(m):
    if len(m) == 1:
        return m[0][0]
    return sum((-1) ** j * m[0][j] * _det_naive([r[:j] + r[j + 1 :] for r in m[1:]]) for j in range(len(m)))


def test_determinant_random_matches_expansion():
    rng = random.Random(7)
    for n in range(1, 8):
        m = [[rng.randint(-9, 9) for _ in range(n)] for _ in range(n)]
        assert determinant(m) == _det_naive(m)


def test_det_8x8_product_property():
    rng = random.Random(3)
    a = [[rng.randint(-3, 3) for _ in range(8)] for _ in range(8)]
    b = [[rng.randint(-3, 3) for _ in range(8)] for _ in range(8)]
    assert determinant(matmul(a, b)) == determinant(a) * determinant(b)


def test_validation_and_no_mutation():
    for bad in ([], [[]], [[1, 2], [3]]):
        with pytest.raises(ValueError):
            transpose(bad)
    with pytest.raises(ValueError):
        determinant([[1, 2, 3], [4, 5, 6]])
    with pytest.raises(ValueError):
        identity(0)
    m = [[4, 3], [6, 3]]
    before = copy.deepcopy(m)
    determinant(m)
    transpose(m)
    assert m == before
