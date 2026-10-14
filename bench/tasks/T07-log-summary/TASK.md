Implement `summarize(lines)` in `src/logsum/summary.py`. `lines` is an iterable of access-log lines in the combined format:

```
203.0.113.9 - - [10/Oct/2026:13:55:36 +0000] "GET /index.html HTTP/1.1" 200 2326 "-" "curl/8.0"
```

Return a dict:
- `total`: number of well-formed lines.
- `status`: dict counting status classes, keys `"2xx"`, `"3xx"`, `"4xx"`, `"5xx"` (only classes that occur).
- `top_paths`: list of the 3 most requested paths (without the query string), most frequent first; ties in alphabetical order.
- `unique_ips`: number of distinct client IPs.
- `bytes`: total response bytes; a size of `-` counts as 0.
- `malformed`: number of lines that do not match the format (skipped, not counted in the other fields). Blank lines are ignored entirely.

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
