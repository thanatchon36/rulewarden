import random
import statistics

import pytest

from numstats import median, mode, percentile


def test_median_matches_statistics():
    rng = random.Random(5)
    for n in range(1, 30):
        xs = [rng.randint(-50, 50) for _ in range(n)]
        assert median(xs) == statistics.median(xs)


def test_median_does_not_mutate():
    xs = [3, 1, 2]
    median(xs)
    assert xs == [3, 1, 2]


def test_mode():
    assert mode([3, 3, 1, 1, 2]) == 1
    assert mode(["b", "a", "b"]) == "b"
    assert mode([7]) == 7


def test_percentile_values():
    xs = [15, 20, 35, 40, 50]
    assert percentile(xs, 0) == 15 and percentile(xs, 100) == 50
    assert percentile(xs, 40) == 29.0
    assert percentile([1, 2, 3, 4], 50) == 2.5


def test_errors():
    for fn in (median, mode):
        with pytest.raises(ValueError):
            fn([])
    for p in (-1, 101):
        with pytest.raises(ValueError):
            percentile([1, 2], p)
    with pytest.raises(ValueError):
        percentile([], 10)
