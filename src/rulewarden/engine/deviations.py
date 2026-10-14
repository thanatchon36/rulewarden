"""Inline deviations (P8): `rulewarden: deviate <ID> reason="…" approved-by="@h" expires=YYYY-MM-DD`."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date

MARKER_RE = re.compile(r"rulewarden:\s*deviate\s+(?P<id>[A-Z][A-Z0-9-]*)(?P<rest>[^\n]*)")
_KV_RE = re.compile(r'(?P<k>[a-z-]+)=(?:"(?P<q>[^"]*)"|(?P<v>[^\s"]+))')


@dataclass(frozen=True)
class Deviation:
    rule_id: str
    path: str
    line: int
    reason: str
    approved_by: str
    expires: date | None
    malformed: str = ""

    @property
    def fingerprint(self) -> str:
        key = (
            f"{self.path}\0{self.rule_id}\0{self.reason}\0{self.approved_by}\0{self.expires or ''}"
        )
        return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_line(path: str, lineno: int, text: str) -> Deviation | None:
    m = MARKER_RE.search(text)
    if not m:
        return None
    kv = {
        mm.group("k"): mm.group("q") if mm.group("q") is not None else mm.group("v")
        for mm in _KV_RE.finditer(m["rest"])
    }
    problems = []
    reason = kv.get("reason", "")
    approver = kv.get("approved-by", "")
    if not reason.strip():
        problems.append("missing reason")
    if not approver.strip():
        problems.append("missing approved-by")
    expires: date | None = None
    if "expires" in kv:
        try:
            expires = date.fromisoformat(kv["expires"])
        except ValueError:
            problems.append(f"bad expires {kv['expires']!r}")
    return Deviation(
        rule_id=m["id"],
        path=path,
        line=lineno,
        reason=reason,
        approved_by=approver,
        expires=expires,
        malformed="; ".join(problems),
    )


def scan(path: str, content: str) -> list[Deviation]:
    out: list[Deviation] = []
    if "rulewarden:" not in content:
        return out
    for i, line in enumerate(content.split("\n"), start=1):
        d = parse_line(path, i, line)
        if d is not None:
            out.append(d)
    return out


def covering(devs: list[Deviation], rule_id: str, line: int | None) -> Deviation | None:
    """A deviation applies to a finding on the same line or on the line directly below it."""
    for d in devs:
        if d.rule_id == rule_id and (line is None or d.line in (line, line - 1)):
            return d
    return None
