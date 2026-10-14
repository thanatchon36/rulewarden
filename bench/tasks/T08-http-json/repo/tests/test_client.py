from httpkit import HTTPStatusError


def test_error_is_exception():
    assert issubclass(HTTPStatusError, Exception)
