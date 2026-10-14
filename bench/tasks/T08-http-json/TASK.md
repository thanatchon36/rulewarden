Implement `fetch_json(url, timeout=5.0, retries=0)` and the exception class `HTTPStatusError` in `src/httpkit/client.py`.

- Send a GET request with headers `Accept: application/json` and `User-Agent: httpkit/1.0`, and return the decoded JSON body.
- `HTTPStatusError(status, url)` must be an `Exception` subclass with attributes `status` (int) and `url` (str). Raise it for any non-2xx response.
- A 5xx response is retried immediately, up to `retries` extra attempts; 4xx responses are never retried. If all attempts fail, raise `HTTPStatusError` for the last response.
- Raise `ValueError` if the body is not valid JSON.
- Network errors (connection refused, timeouts) propagate as the original exception.

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
