import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from httpkit import HTTPStatusError, fetch_json


class State:
    hits = {}
    headers = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        State.hits[self.path] = State.hits.get(self.path, 0) + 1
        State.headers[self.path] = dict(self.headers)
        n = State.hits[self.path]
        if self.path == "/ok":
            self._send(200, json.dumps({"a": [1, 2]}))
        elif self.path == "/flaky" and n < 3:
            self._send(503, "busy")
        elif self.path == "/flaky":
            self._send(200, "[1]")
        elif self.path == "/down":
            self._send(500, "no")
        elif self.path == "/missing":
            self._send(404, "nope")
        elif self.path == "/bad":
            self._send(200, "{oops")
        else:
            self._send(204, "null")

    def _send(self, code, body):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def base():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(autouse=True)
def reset():
    State.hits.clear()
    State.headers.clear()


def test_ok_and_headers(base):
    assert fetch_json(base + "/ok") == {"a": [1, 2]}
    h = {k.lower(): v for k, v in State.headers["/ok"].items()}
    assert h["accept"] == "application/json" and h["user-agent"] == "httpkit/1.0"


def test_retries_on_5xx(base):
    assert fetch_json(base + "/flaky", retries=2) == [1]
    assert State.hits["/flaky"] == 3


def test_gives_up_after_retries(base):
    with pytest.raises(HTTPStatusError) as e:
        fetch_json(base + "/down", retries=1)
    assert e.value.status == 500 and e.value.url == base + "/down" and State.hits["/down"] == 2


def test_4xx_not_retried(base):
    with pytest.raises(HTTPStatusError) as e:
        fetch_json(base + "/missing", retries=3)
    assert e.value.status == 404 and State.hits["/missing"] == 1


def test_invalid_json(base):
    with pytest.raises(ValueError):
        fetch_json(base + "/bad")


def test_connection_refused():
    with pytest.raises(OSError):
        fetch_json("http://127.0.0.1:9/", timeout=1)
