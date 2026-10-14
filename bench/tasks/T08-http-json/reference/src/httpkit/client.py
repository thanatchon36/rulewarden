import json
import urllib.error
import urllib.request

_HEADERS = {"Accept": "application/json", "User-Agent": "httpkit/1.0"}


class HTTPStatusError(Exception):
    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.url = url


def _get(url: str, timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def fetch_json(url: str, timeout: float = 5.0, retries: int = 0) -> object:
    """GET `url` and decode JSON; retry 5xx up to `retries` times."""
    for attempt in range(retries + 1):
        status, body = _get(url, timeout)
        if 200 <= status < 300:
            return json.loads(body)
        if status < 500 or attempt == retries:
            raise HTTPStatusError(status, url)
    raise AssertionError("unreachable")
