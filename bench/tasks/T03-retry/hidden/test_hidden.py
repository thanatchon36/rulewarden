import pytest

from resilience import retry


class Flaky:
    def __init__(self, failures, exc=ConnectionError):
        self.failures = failures
        self.exc = exc
        self.calls = 0

    def __call__(self, x):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exc(f"fail {self.calls}")
        return x * 2


def test_retries_until_success_with_backoff():
    sleeps = []
    f = Flaky(2)
    wrapped = retry(5, (ConnectionError,), delay=1.0, backoff=3.0, sleep=sleeps.append)(f)
    assert wrapped(21) == 42
    assert f.calls == 3 and sleeps == [1.0, 3.0] and wrapped.last_attempts == 3


def test_reraises_last_exception_after_exhaustion():
    sleeps = []
    f = Flaky(10)
    wrapped = retry(3, (ConnectionError,), delay=0.5, sleep=sleeps.append)(f)
    with pytest.raises(ConnectionError, match="fail 3"):
        wrapped(1)
    assert f.calls == 3 and sleeps == [0.5, 1.0] and wrapped.last_attempts == 3


def test_unlisted_exception_propagates_immediately():
    f = Flaky(1, exc=KeyError)
    wrapped = retry(4, (ConnectionError,), sleep=lambda s: None)(f)
    with pytest.raises(KeyError):
        wrapped(1)
    assert f.calls == 1 and wrapped.last_attempts == 1


def test_zero_delay_never_sleeps():
    calls = []
    f = Flaky(2)
    assert retry(3, sleep=calls.append)(f)(2) == 4
    assert calls == []


def test_metadata_preserved():
    @retry(2)
    def documented():
        """Doc."""
        return 1

    assert documented.__name__ == "documented" and documented.__doc__ == "Doc."


def test_last_attempts_resets_per_invocation():
    f = Flaky(1)
    wrapped = retry(3, sleep=lambda s: None)(f)
    wrapped(1)
    assert wrapped.last_attempts == 2
    wrapped(1)
    assert wrapped.last_attempts == 1


@pytest.mark.parametrize("kwargs", [{"times": 0}, {"times": 2, "delay": -1}, {"times": 2, "backoff": 0.5}])
def test_invalid_arguments(kwargs):
    with pytest.raises(ValueError):
        retry(**kwargs)
