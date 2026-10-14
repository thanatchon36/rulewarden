"""Append-only, hash-chained audit log (P9). The timestamp is the only non-deterministic field."""

from __future__ import annotations

import fcntl
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from rulewarden import __version__
from rulewarden.config import AUDIT_FILE
from rulewarden.engine.report import Result, ordered

GENESIS = "0" * 64


def _line_hash(line: str) -> str:
    return hashlib.sha256(line.rstrip("\n").encode("utf-8")).hexdigest()


def _last_hash(path: Path) -> str:
    if not path.exists() or path.stat().st_size == 0:
        return GENESIS
    with path.open("rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        block = min(size, 1 << 16)
        fh.seek(size - block)
        tail = fh.read().decode("utf-8", errors="replace").rstrip("\n").split("\n")[-1]
    return _line_hash(tail)


@dataclass(frozen=True)
class Event:
    harness: str
    event: str
    session_id: str = ""
    elapsed_ms: int = 0
    note: str = ""
    outcome: str = ""


def append(root: Path, result: Result, ev: Event) -> dict[str, object]:
    path = root / AUDIT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            entry: dict[str, object] = {
                "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "prev": _last_hash(path),
                "rulewarden": __version__,
                "harness": ev.harness,
                "event": ev.event,
                "session_id": ev.session_id,
                "diff_sha256": result.diff_sha256,
                "ruleset_sha256": result.ruleset_sha256,
                "exit_code": result.exit_code,
                "status": result.status,
                "counts": result.counts,
                "outcomes": dict(sorted(result.outcomes.items())),
                "findings": sorted({f.rule_id for f in result.findings}),
                "deviations": len(result.deviations_applied),
                "elapsed_ms": ev.elapsed_ms,
            }
            if ev.note:
                entry["note"] = ev.note
            if ev.outcome:
                entry["outcome"] = ev.outcome
                entry["unresolved"] = [f.render() for f in ordered(result.findings)]
            fh.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
            fh.flush()
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    return entry


def read(root: Path) -> Iterator[dict[str, object]]:
    path = root / AUDIT_FILE
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def verify_chain(root: Path) -> tuple[bool, int, str]:
    """Return (intact, entries, message). Detects edited, removed or reordered lines."""
    path = root / AUDIT_FILE
    if not path.exists():
        return True, 0, "no audit log"
    prev = GENESIS
    n = 0
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                return False, n, f"line {n} is not JSON"
            if entry.get("prev") != prev:
                return False, n, f"chain broken at line {n}"
            prev = _line_hash(line)
    return True, n, "intact"
