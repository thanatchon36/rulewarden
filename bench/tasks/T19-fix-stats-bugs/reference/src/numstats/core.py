from collections import Counter


def median(values):
    """Middle value of the sorted values; mean of the two middle values for even length.

    Raises ValueError for an empty sequence.
    """
    if not values:
        raise ValueError("median of an empty sequence")
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


def mode(values):
    """Most common value; on ties, the smallest of the tied values. ValueError if empty."""
    if not values:
        raise ValueError("mode of an empty sequence")
    counts = Counter(values)
    top = max(counts.values())
    return min(v for v, c in counts.items() if c == top)


def percentile(values, p):
    """p-th percentile (0 <= p <= 100) with linear interpolation between closest ranks.

    Uses rank = p / 100 * (n - 1) on the sorted values. ValueError if empty or p out of range.
    """
    if not values or not 0 <= p <= 100:
        raise ValueError("need values and 0 <= p <= 100")
    s = sorted(values)
    rank = p / 100 * (len(s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (rank - lo)
