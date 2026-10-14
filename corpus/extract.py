"""Extract rule-like lines from the collected files into corpus/data/rules.csv.

Uses the same extractor as `rulewarden compile`. Lines that match the shipped secrets
pack are stored as a SHA-256 only; e-mail addresses and @handles are masked.
"""

from __future__ import annotations

import csv
import hashlib
import re
import sys
from importlib import resources
from pathlib import Path

import yaml

from rulewarden.compile.extract import extract
from rulewarden.engine.regexsafe import compile_safe

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = HERE / ".cache" / "blobs"

FIELDS = ("rule_id", "file_id", "stratum", "line", "text", "text_sha256", "redacted")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_HANDLE_RE = re.compile(r"(?<![\w@/.])@[A-Za-z0-9][A-Za-z0-9-]{1,38}\b")


def secret_patterns() -> list[re.Pattern[str]]:
    pack = yaml.safe_load(
        (resources.files("rulewarden.packs") / "secrets.yaml").read_text(encoding="utf-8")
    )
    out: list[re.Pattern[str]] = []
    for rule in pack["rules"]:
        check = rule.get("check") or {}
        pats = check.get("patterns") or ([check["pattern"]] if "pattern" in check else [])
        out.extend(compile_safe(p) for p in pats)
    return out


def scrub(text: str, secrets: list[re.Pattern[str]]) -> tuple[str, bool]:
    if any(p.search(text) for p in secrets):
        return "", True
    masked = _EMAIL_RE.sub("<email>", text)
    masked = _HANDLE_RE.sub("@<handle>", masked)
    return masked, False


def main() -> int:
    with (DATA / "files.csv").open(encoding="utf-8", newline="") as fh:
        files = list(csv.DictReader(fh))
    secrets = secret_patterns()
    rows: list[dict[str, str]] = []
    for f in files:
        blob = CACHE / f"{f['blob_sha']}.txt"
        if not blob.exists():
            print(f"missing cache for {f['file_id']}; re-run collect.py", file=sys.stderr)
            return 1
        text = blob.read_bytes().decode("utf-8", errors="replace")
        for rl in extract(text):
            clean, redacted = scrub(rl.text, secrets)
            rows.append(
                {
                    "rule_id": f"{f['file_id']}:L{rl.lineno}",
                    "file_id": f["file_id"],
                    "stratum": f["stratum"],
                    "line": str(rl.lineno),
                    "text": clean,
                    "text_sha256": hashlib.sha256(rl.text.encode("utf-8")).hexdigest(),
                    "redacted": "1" if redacted else "0",
                }
            )
    with (DATA / "rules.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rule-like lines from {len(files)} files", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
