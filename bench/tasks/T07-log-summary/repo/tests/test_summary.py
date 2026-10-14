from logsum import summarize

LINE = '203.0.113.9 - - [10/Oct/2026:13:55:36 +0000] "GET /index.html HTTP/1.1" 200 2326 "-" "curl/8.0"'


def test_one_line():
    assert summarize([LINE])["total"] == 1
