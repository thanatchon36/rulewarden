Implement the decorator factory `retry` in `src/resilience/retry.py`:

```python
def retry(times, exceptions=(Exception,), delay=0.0, backoff=2.0, sleep=time.sleep): ...
```

- The decorated function is called at most `times` times.
- If a call raises an exception that is an instance of one of `exceptions`, and attempts remain, wait `delay * backoff ** (attempt - 1)` seconds by calling `sleep(seconds)` (attempt counts from 1), then call again. Do not call `sleep` when `delay` is 0.
- If the last attempt fails, re-raise that exception unchanged.
- Exceptions that are not in `exceptions` propagate immediately, without retrying.
- Raise `ValueError` at decoration time if `times < 1`, `delay < 0` or `backoff < 1`.
- The wrapper keeps the wrapped function's `__name__` and `__doc__`, and exposes `wrapper.last_attempts`: the number of calls made during the most recent invocation.

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
