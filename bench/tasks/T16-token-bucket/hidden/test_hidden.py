import math

import pytest

from ratelimit import TokenBucket


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


def test_acquire_refill_and_cap():
    clk = Clock()
    b = TokenBucket(2.0, 4, clock=clk)
    assert b.tokens == 4.0
    assert b.try_acquire(3) and math.isclose(b.tokens, 1.0)
    assert not b.try_acquire(2) and math.isclose(b.tokens, 1.0)
    clk.t += 0.5
    assert b.try_acquire(2) and math.isclose(b.tokens, 0.0)
    clk.t += 100
    assert b.tokens == 4.0


def test_wait_time():
    clk = Clock()
    b = TokenBucket(4.0, 10, clock=clk)
    b.try_acquire(10)
    assert math.isclose(b.wait_time(2), 0.5)
    assert math.isclose(b.tokens, 0.0)
    clk.t += 0.25
    assert math.isclose(b.wait_time(2), 0.25) and b.wait_time(1) == 0.0


def test_fractional_rates():
    clk = Clock()
    b = TokenBucket(0.1, 1, clock=clk)
    assert b.try_acquire()
    clk.t += 9.99
    assert not b.try_acquire()
    clk.t += 0.02
    assert b.try_acquire()


@pytest.mark.parametrize(("rate", "cap"), [(0, 1), (1, 0), (-1, 5)])
def test_invalid_construction(rate, cap):
    with pytest.raises(ValueError):
        TokenBucket(rate, cap)


def test_invalid_n():
    b = TokenBucket(1, 2, clock=Clock())
    for n in (0, -1, 3):
        with pytest.raises(ValueError):
            b.try_acquire(n)
        with pytest.raises(ValueError):
            b.wait_time(n)
