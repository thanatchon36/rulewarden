from logsum import summarize


def line(ip, path, status, size, method="GET"):
    return f'{ip} - - [10/Oct/2026:13:55:36 +0000] "{method} {path} HTTP/1.1" {status} {size} "-" "ua/1.0"'


def test_summary():
    lines = [
        line("10.0.0.1", "/a?x=1", 200, 100),
        line("10.0.0.2", "/a", 200, 50),
        line("10.0.0.1", "/b", 404, "-"),
        line("10.0.0.3", "/c", 500, 10, method="POST"),
        line("10.0.0.3", "/b", 301, 0),
        line("10.0.0.4", "/d", 200, 1),
        "garbage line",
        "",
        '10.0.0.9 - - [bad date "GET / HTTP/1.1" 200 1 "-" "x"',
    ]
    s = summarize(lines)
    assert s["total"] == 6
    assert s["status"] == {"2xx": 3, "3xx": 1, "4xx": 1, "5xx": 1}
    assert s["top_paths"] == ["/a", "/b", "/c"]
    assert s["unique_ips"] == 4
    assert s["bytes"] == 161
    assert s["malformed"] == 2


def test_empty_and_generator():
    s = summarize(x for x in ["", "  "])
    assert s == {"total": 0, "status": {}, "top_paths": [], "unique_ips": 0, "bytes": 0, "malformed": 0}


def test_fewer_than_three_paths_and_trailing_newlines():
    s = summarize([line("1.1.1.1", "/only", 200, 5) + "\n"])
    assert s["top_paths"] == ["/only"] and s["status"] == {"2xx": 1}


def test_ipv6_and_ties():
    lines = [line("2001:db8::1", p, 200, 1) for p in ["/z", "/y", "/x", "/w"]]
    s = summarize(lines)
    assert s["top_paths"] == ["/w", "/x", "/y"] and s["unique_ips"] == 1
