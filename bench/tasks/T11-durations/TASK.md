Implement in `src/durations/core.py`:

`parse_duration(text) -> int` returns seconds.
- Unit form: one or more `<integer><unit>` parts with units `d`, `h`, `m`, `s` (case-insensitive), in that order, each unit at most once, optionally separated by spaces: `"1d2h"`, `"90s"`, `"2h 15m"`, `"1D 1S"`.
- Clock form: `"MM:SS"` or `"HH:MM:SS"` where minutes and seconds are two digits below 60 (hours any number of digits).
- Leading and trailing whitespace is ignored. Anything else (empty string, unknown unit, repeated or out-of-order unit, negative numbers, `"1.5h"`) raises `ValueError`.

`format_duration(seconds) -> str`: e.g. `93784` → `"1d 2h 3m 4s"`; omit zero parts; `0` → `"0s"`; a negative or non-int argument raises `ValueError`.

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
