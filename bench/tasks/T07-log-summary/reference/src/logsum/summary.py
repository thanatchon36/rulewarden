import re
from collections import Counter
from collections.abc import Iterable

_LINE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[[^\]]+\] "(?P<method>[A-Z]+) (?P<path>\S+) [^"]*" '
    r'(?P<status>\d{3}) (?P<size>\d+|-) "[^"]*" "[^"]*"$'
)


def summarize(lines: Iterable[str]) -> dict[str, object]:
    """Count requests, status classes, top paths, unique IPs and bytes in access-log lines."""
    paths: Counter[str] = Counter()
    status: Counter[str] = Counter()
    ips: set[str] = set()
    total = size = malformed = 0
    for raw in lines:
        text = raw.strip()
        if not text:
            continue
        m = _LINE.match(text)
        if m is None:
            malformed += 1
            continue
        total += 1
        ips.add(m["ip"])
        paths[m["path"].split("?", 1)[0]] += 1
        status[f"{m['status'][0]}xx"] += 1
        size += 0 if m["size"] == "-" else int(m["size"])
    top = sorted(paths.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return {
        "total": total,
        "status": dict(sorted(status.items())),
        "top_paths": [p for p, _ in top],
        "unique_ips": len(ips),
        "bytes": size,
        "malformed": malformed,
    }
