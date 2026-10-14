import time


class TokenBucket:
    """Token bucket that refills continuously at `rate` tokens per second."""

    def __init__(self, rate, capacity, clock=time.monotonic):
        if rate <= 0 or capacity <= 0:
            raise ValueError("rate and capacity must be positive")
        self._rate = float(rate)
        self._capacity = float(capacity)
        self._clock = clock
        self._tokens = float(capacity)
        self._stamp = clock()

    def _refill(self):
        now = self._clock()
        self._tokens = min(self._capacity, self._tokens + (now - self._stamp) * self._rate)
        self._stamp = now

    def _check(self, n):
        if n <= 0 or n > self._capacity:
            raise ValueError(f"n must be in (0, {self._capacity}]")

    @property
    def tokens(self):
        self._refill()
        return self._tokens

    def try_acquire(self, n=1):
        self._check(n)
        self._refill()
        if self._tokens + 1e-9 < n:
            return False
        self._tokens = max(0.0, self._tokens - n)
        return True

    def wait_time(self, n=1):
        self._check(n)
        self._refill()
        return max(0.0, (n - self._tokens) / self._rate)
