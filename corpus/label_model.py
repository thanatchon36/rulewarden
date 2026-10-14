"""Model-assisted labels: two independent passes with a fixed prompt (corpus/README.md).

Runs `claude -p` with no tools, no settings files and no MCP servers, in an empty
directory. Raw responses are kept in corpus/data/model_raw/ for audit; labels go to
corpus/data/labels_model.csv. Pass 2 sees each batch in reverse order. Resumable.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RAW = DATA / "model_raw"
PROMPT = (HERE / "prompts" / "label_v1.txt").read_text(encoding="utf-8")
MODEL = "haiku"
BATCH = 80
WORKERS = 4
CATEGORIES = ["style", "tooling", "scope", "process", "testing", "security", "voice", "other"]
TIERS = ["deterministic", "heuristic", "undecidable"]
SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "is_rule": {"type": "boolean"},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "decidability": {"type": "string", "enum": TIERS},
                },
                "required": ["id", "is_rule", "category", "decidability"],
            },
        }
    },
    "required": ["labels"],
}


def call(lines: list[tuple[int, str]], workdir: str) -> dict[str, object]:
    body = "\n".join(f"{i}\t{t}" for i, t in lines)
    cmd = [
        "claude",
        "-p",
        "--model",
        MODEL,
        "--restricted",
        "--tools",
        "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--max-turns",
        "3",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(SCHEMA),
    ]
    proc = subprocess.run(
        cmd, input=PROMPT + body, capture_output=True, text=True, cwd=workdir, timeout=600
    )
    data: dict[str, object] = json.loads(proc.stdout)
    return data


def run_batch(pass_no: int, idx: int, batch: list[tuple[int, str]], workdir: str) -> None:
    out = RAW / f"pass{pass_no}" / f"batch_{idx:04d}.json"
    if out.exists():
        return
    lines = list(reversed(batch)) if pass_no == 2 else batch
    for _attempt in range(3):
        try:
            data = call(lines, workdir)
        except (subprocess.TimeoutExpired, ValueError) as exc:
            print(f"pass {pass_no} batch {idx}: {exc}", file=sys.stderr)
            continue
        so = data.get("structured_output")
        labels = so.get("labels") if isinstance(so, dict) else None
        if not data.get("is_error") and isinstance(labels, list):
            got = {lab.get("id") for lab in labels if isinstance(lab, dict)}
            if got >= {i for i, _ in batch}:
                record = {
                    "prompt_file": "corpus/prompts/label_v1.txt",
                    "model": sorted((data.get("modelUsage") or {}).keys()),  # type: ignore[union-attr]
                    "ids": [i for i, _ in lines],
                    "labels": labels,
                }
                out.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
                return
        print(f"pass {pass_no} batch {idx}: incomplete response, retrying", file=sys.stderr)
    print(f"pass {pass_no} batch {idx}: gave up after 3 attempts", file=sys.stderr)


def main() -> int:
    with (DATA / "rules.csv").open(encoding="utf-8", newline="") as fh:
        rules = [r for r in csv.DictReader(fh) if r["redacted"] == "0"]
    items = list(enumerate((r["text"] for r in rules), start=1))
    batches = [items[i : i + BATCH] for i in range(0, len(items), BATCH)]
    with tempfile.TemporaryDirectory() as workdir:
        for pass_no in (1, 2):
            (RAW / f"pass{pass_no}").mkdir(parents=True, exist_ok=True)
            with ThreadPoolExecutor(WORKERS) as pool:
                n = len(batches)
                list(pool.map(run_batch, [pass_no] * n, range(n), batches, [workdir] * n))
    labels: dict[int, dict[str, str]] = {}
    complete = True
    for pass_no in (1, 2):
        for idx in range(len(batches)):
            f = RAW / f"pass{pass_no}" / f"batch_{idx:04d}.json"
            if not f.exists():
                complete = False
                continue
            for lab in json.loads(f.read_text(encoding="utf-8"))["labels"]:
                row = labels.setdefault(int(lab["id"]), {})
                row[f"is_rule_p{pass_no}"] = "1" if lab["is_rule"] else "0"
                row[f"category_p{pass_no}"] = lab["category"]
                row[f"decidability_p{pass_no}"] = lab["decidability"]
    fields = ["rule_id"] + [
        f"{k}_p{n}" for n in (1, 2) for k in ("is_rule", "category", "decidability")
    ]
    with (DATA / "labels_model.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for i, r in enumerate(rules, start=1):
            w.writerow(
                {"rule_id": r["rule_id"], **{k: labels.get(i, {}).get(k, "") for k in fields[1:]}}
            )
    print(
        f"{len(rules)} lines, {len(batches)} batches per pass, complete={complete}", file=sys.stderr
    )
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())
