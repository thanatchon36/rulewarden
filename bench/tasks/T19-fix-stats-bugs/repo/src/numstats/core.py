from collections import Counter


def median(values):
    """Middle value of the sorted values; mean of the two middle values for even length.

    Raises ValueError for an empty sequence.
    """
    n = len(values)
    mid = n // 2
    if n % 2:
        return values[mid]
    return (values[mid] + values[mid + 1]) / 2


def mode(values):
    """Most common value; on ties, the smallest of the tied values. ValueError if empty."""
    counts = Counter(values)
    return counts.most_common(1)[0][0]


def percentile(values, p):
    """p-th percentile (0 <= p <= 100) with linear interpolation between closest ranks.

    Uses rank = p / 100 * (n - 1) on the sorted values. ValueError if empty or p out of range.
    """
    s = sorted(values)
    rank = p / 100 * len(s)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (rank - lo)
