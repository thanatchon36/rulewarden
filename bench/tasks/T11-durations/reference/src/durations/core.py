import re

_UNITS = re.compile(
    r"(?:(?P<d>\d+)d)?\s*(?:(?P<h>\d+)h)?\s*(?:(?P<m>\d+)m)?\s*(?:(?P<s>\d+)s)?", re.IGNORECASE
)
_CLOCK = re.compile(r"(?:(?P<h>\d+):)?(?P<m>[0-5]\d):(?P<s>[0-5]\d)")
_SECONDS = {"d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_duration(text: str) -> int:
    """Seconds in a `1d2h3m4s`-style or `[HH:]MM:SS` duration."""
    s = text.strip()
    clock = _CLOCK.fullmatch(s)
    if clock:
        return int(clock["h"] or 0) * 3600 + int(clock["m"]) * 60 + int(clock["s"])
    m = _UNITS.fullmatch(s)
    if not s or m is None or not any(m.groupdict().values()):
        raise ValueError(f"invalid duration: {text!r}")
    return sum(int(v) * _SECONDS[k] for k, v in m.groupdict().items() if v)


def format_duration(seconds: int) -> str:
    """Format seconds as `1d 2h 3m 4s`, omitting zero parts."""
    if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds < 0:
        raise ValueError(f"seconds must be a non-negative int, got {seconds!r}")
    parts = []
    for unit, size in _SECONDS.items():
        n, seconds = divmod(seconds, size)
        if n:
            parts.append(f"{n}{unit}")
    return " ".join(parts) or "0s"
