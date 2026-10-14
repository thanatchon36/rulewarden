from ratelimit import TokenBucket


def test_starts_full():
    b = TokenBucket(1, 3, clock=lambda: 0.0)
    assert b.try_acquire(3)
