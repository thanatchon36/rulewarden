"""Static ReDoS screen: reject patterns whose unbounded repeats nest (star height >= 2)."""

from __future__ import annotations

import importlib
import re
from typing import Any

from rulewarden.errors import SchemaError


def _import(*names: str) -> Any:
    for name in names:
        try:
            return importlib.import_module(name)
        except ImportError:  # pragma: no cover - depends on the Python version
            continue
    raise ImportError(names[-1])  # pragma: no cover


_sre_c = _import("re._constants", "sre_constants")
_sre_p = _import("re._parser", "sre_parse")

_REPEATS = {_sre_c.MAX_REPEAT, _sre_c.MIN_REPEAT, getattr(_sre_c, "POSSESSIVE_REPEAT", None)} - {
    None
}
_UNBOUNDED_MIN = 50
MAX_PATTERN_CHARS = 2000

_FLAG_MAP = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "x": re.VERBOSE}


def _unbounded(max_count: int) -> bool:
    return bool(max_count == _sre_c.MAXREPEAT or max_count > _UNBOUNDED_MIN)


def _height(items: Any) -> int:
    best = 0
    for op, av in items:
        if op in _REPEATS:
            _lo, hi, sub = av
            inner = _height(sub)
            best = max(best, inner + (1 if _unbounded(hi) else 0))
        elif op is _sre_c.SUBPATTERN:
            best = max(best, _height(av[-1]))
        elif op is _sre_c.BRANCH:
            for alt in av[1]:
                best = max(best, _height(alt))
        elif op in (_sre_c.ASSERT, _sre_c.ASSERT_NOT):
            best = max(best, _height(av[1]))
        elif op is getattr(_sre_c, "ATOMIC_GROUP", None):
            best = max(best, _height(av))
    return best


def compile_safe(pattern: str, flags: list[str] | tuple[str, ...] | None = None) -> re.Pattern[str]:
    """Compile a rule pattern after rejecting shapes known to backtrack catastrophically."""
    if len(pattern) > MAX_PATTERN_CHARS:
        raise SchemaError(f"pattern longer than {MAX_PATTERN_CHARS} characters")
    f = 0
    for fl in flags or ():
        if fl not in _FLAG_MAP:
            raise SchemaError(f"unknown regex flag {fl!r} (allowed: i, m, s, x)")
        f |= _FLAG_MAP[fl]
    try:
        parsed = _sre_p.parse(pattern, f)
    except re.error as exc:
        raise SchemaError(f"invalid regex {pattern!r}: {exc}") from exc
    if _height(parsed) >= 2:
        raise SchemaError(
            f"regex {pattern!r} nests unbounded repeats (ReDoS risk); rewrite it without nesting"
        )
    if "(?P=" in pattern or re.search(r"\\[1-9]", pattern):
        raise SchemaError(f"regex {pattern!r} uses backreferences, which are not allowed")
    return re.compile(pattern, f)
