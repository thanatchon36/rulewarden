Implement `TokenBucket(rate, capacity, clock=time.monotonic)` in `src/ratelimit/bucket.py`:

- The bucket starts full with `capacity` tokens and refills continuously at `rate` tokens per second, never above `capacity`.
- `try_acquire(n=1) -> bool`: if at least `n` tokens are available, remove them and return `True`; otherwise return `False` and remove nothing.
- `wait_time(n=1) -> float`: seconds until `n` tokens will be available (0.0 if available now); does not remove tokens.
- `tokens` property: the current (refilled) token count as a float.
- `rate` and `capacity` must be positive, and `n` must be positive and at most `capacity`, else `ValueError`.

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
