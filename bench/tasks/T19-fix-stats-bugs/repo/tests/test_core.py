import pytest

from numstats import median, mode, percentile


def test_median():
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 3, 2]) == 2.5


def test_mode_ties_pick_smallest():
    assert mode([3, 3, 1, 1, 2]) == 1


def test_percentile():
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([10, 20], 25) == 12.5
    assert percentile([5, 1, 3], 100) == 5


def test_empty_raises():
    for fn in (median, mode):
        with pytest.raises(ValueError):
            fn([])
    with pytest.raises(ValueError):
        percentile([], 50)
