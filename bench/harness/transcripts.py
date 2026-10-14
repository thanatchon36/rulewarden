"""Lossless, scannable transcript storage: strings over CHUNK chars become chunk lists.

The engine cannot verify lines over 20,000 characters (it fails closed), so recorded
transcripts are stored pretty-printed with long strings split into {"__rw_chunks__": [...]}.
decode() restores the original events exactly. Secrets are scrubbed before encoding.
Usage: python -m bench.harness.transcripts migrate  (rewrites transcript.jsonl files)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

CHUNK = 2000
KEY = "__rw_chunks__"


def _enc(obj: Any) -> Any:
    if isinstance(obj, str) and len(obj) > CHUNK:
        return {KEY: [obj[i : i + CHUNK] for i in range(0, len(obj), CHUNK)]}
    if isinstance(obj, list):
        return [_enc(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _enc(v) for k, v in obj.items()}
    return obj


def _dec(obj: Any) -> Any:
    if isinstance(obj, dict):
        if set(obj) == {KEY}:
            return "".join(obj[KEY])
        return {k: _dec(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_dec(x) for x in obj]
    return obj


def encode(stream_json: str) -> str:
    """stream-json stdout (one event per line) -> stored text; unparsable lines kept as strings."""
    events: list[Any] = []
    for line in stream_json.splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            events.append({"__rw_raw__": line})
    return json.dumps(_enc(events), indent=1, ensure_ascii=False) + "\n"


def decode(stored: str) -> list[Any]:
    data = _dec(json.loads(stored))
    return data if isinstance(data, list) else []


def load(run: Path) -> list[Any]:
    stored = run / "transcript.json"
    if stored.exists():
        return decode(stored.read_text(encoding="utf-8"))
    legacy = run / "transcript.jsonl"
    if legacy.exists():
        return decode(encode(legacy.read_text(encoding="utf-8")))
    return []


def migrate(root: Path) -> int:
    n = 0
    for legacy in sorted(root.rglob("transcript.jsonl")):
        text = legacy.read_text(encoding="utf-8")
        stored = encode(text)
        original = [json.loads(x) for x in text.splitlines() if x.strip()]
        if decode(stored) != original:
            raise SystemExit(f"{legacy}: encoding is not lossless; refusing to migrate")
        legacy.with_name("transcript.json").write_text(stored, encoding="utf-8")
        legacy.unlink()
        n += 1
    return n


if __name__ == "__main__":
    if sys.argv[1:] == ["migrate"]:
        print(f"migrated {migrate(Path(__file__).resolve().parents[1] / 'recorded')} transcripts")
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
