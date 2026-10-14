import functools
import time


def retry(times, exceptions=(Exception,), delay=0.0, backoff=2.0, sleep=time.sleep):
    """Retry a function on the given exceptions with exponential backoff."""
    if times < 1 or delay < 0 or backoff < 1:
        raise ValueError("need times >= 1, delay >= 0 and backoff >= 1")

    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, times + 1):
                wrapper.last_attempts = attempt
                try:
                    return fn(*args, **kwargs)
                except exceptions:
                    if attempt == times:
                        raise
                    if delay:
                        sleep(delay * backoff ** (attempt - 1))
            raise AssertionError("unreachable")

        wrapper.last_attempts = 0
        return wrapper

    return decorate
