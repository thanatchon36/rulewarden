"""Snapshot this repository's own audit log into paper/data/dogfood_audit.json.

The live log (.rulewarden/audit.jsonl) is git-ignored because committing it would be a
protected-path change on every run. The paper appendix is built from this snapshot, which
records the chain check, per-event and per-rule counts, and the covered time span.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / ".venv" / "bin" / "rulewarden"


def _json(*args: str) -> dict[str, object]:
    proc = subprocess.run(
        [str(BIN), *args, "--format", "json", "--root", str(ROOT)],
        capture_output=True,
        text=True,
        check=True,
    )
    data: dict[str, object] = json.loads(proc.stdout)
    return data


def main() -> int:
    log = ROOT / ".rulewarden" / "audit.jsonl"
    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]
    report = _json("report")
    stats = _json("stats")
    snap = {
        "chain": report["chain"],
        "first_ts": lines[0]["ts"] if lines else None,
        "last_ts": lines[-1]["ts"] if lines else None,
        "by_event": stats["by_event"],
        "by_status": stats["by_status"],
        "rule_fires": stats["rule_fires"],
        "prevented_before_actuation": stats["prevented_before_actuation"],
        "self_correction": stats["self_correction"],
        "never_fired": stats["never_fired"],
    }
    out = ROOT / "paper" / "data" / "dogfood_audit.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({report['chain']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
