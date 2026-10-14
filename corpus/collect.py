"""Collect agent instruction files from GitHub code search (plan: corpus/README.md).

Writes corpus/data/files.csv and corpus/data/collection_log.json. File contents go to
the git-ignored cache corpus/.cache/blobs/; only extracted, scrubbed lines are published.
Needs an authenticated `gh`. Re-running resumes from the cache and skips known files.
"""

from __future__ import annotations

import base64
import csv
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = HERE / ".cache" / "blobs"

STRATA = ("CLAUDE.md", "AGENTS.md", ".cursorrules", "GEMINI.md", ".windsurfrules")
PER_STRATUM = 60
MAX_FILES = 300
MAX_BYTES = 200_000
MAX_PAGES = 10
SEARCH_INTERVAL_S = 6.5

# OSI-approved licences as reported by GitHub's licence detection (SPDX ids).
OSI_ALLOWLIST = frozenset(
    {
        "0BSD",
        "AFL-3.0",
        "AGPL-3.0",
        "Apache-2.0",
        "Artistic-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "BSD-3-Clause-Clear",
        "BSL-1.0",
        "ECL-2.0",
        "EPL-1.0",
        "EPL-2.0",
        "EUPL-1.1",
        "EUPL-1.2",
        "GPL-2.0",
        "GPL-3.0",
        "ISC",
        "LGPL-2.1",
        "LGPL-3.0",
        "MIT",
        "MIT-0",
        "MPL-2.0",
        "MS-PL",
        "MS-RL",
        "NCSA",
        "OSL-3.0",
        "PostgreSQL",
        "UPL-1.0",
        "Unlicense",
        "Zlib",
    }
)

FIELDS = (
    "file_id",
    "stratum",
    "repo",
    "path",
    "blob_sha",
    "commit_sha",
    "license",
    "stars",
    "bytes",
    "collected_at",
)


def gh(*args: str, accept: str | None = None) -> str:
    cmd = ["gh", "api", *args]
    if accept:
        cmd[2:2] = ["-H", f"Accept: {accept}"]
    for attempt in range(4):
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            return proc.stdout
        err = proc.stderr
        if "rate limit" in err.lower() or "403" in err or "429" in err:
            time.sleep(60 * (attempt + 1))
            continue
        raise RuntimeError(f"gh api {' '.join(args)}: {err.strip()[:300]}")
    raise RuntimeError(f"gh api {' '.join(args)}: rate limited after retries")


def search_page(stratum: str, page: int) -> list[dict[str, object]]:
    out = gh(
        "-X",
        "GET",
        "search/code",
        "-f",
        f"q=filename:{stratum}",
        "-f",
        "per_page=100",
        "-f",
        f"page={page}",
    )
    items = json.loads(out).get("items", [])
    return items if isinstance(items, list) else []


def load_existing() -> list[dict[str, str]]:
    path = DATA / "files.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_files(rows: list[dict[str, str]]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / "files.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def fetch_blob(repo: str, sha: str) -> bytes:
    data = json.loads(gh(f"repos/{repo}/git/blobs/{sha}"))
    return base64.b64decode(str(data.get("content", "")))


def collect() -> int:
    rows = load_existing()
    seen_repos = {r["repo"] for r in rows}
    log: dict[str, object] = {"query_date": datetime.now(UTC).strftime("%Y-%m-%d"), "strata": {}}
    strata_log: dict[str, dict[str, int]] = {}
    CACHE.mkdir(parents=True, exist_ok=True)
    for stratum in STRATA:
        have = sum(1 for r in rows if r["stratum"] == stratum)
        skips = {
            "fork": 0,
            "repo_already_sampled": 0,
            "not_exact_filename": 0,
            "too_large": 0,
            "licence_not_osi": 0,
            "error": 0,
        }
        seen_results = 0
        page = 1
        while have < PER_STRATUM and len(rows) < MAX_FILES and page <= MAX_PAGES:
            time.sleep(SEARCH_INTERVAL_S)
            items = search_page(stratum, page)
            page += 1
            if not items:
                break
            for item in items:
                if have >= PER_STRATUM or len(rows) >= MAX_FILES:
                    break
                seen_results += 1
                repo_obj = item.get("repository") or {}
                assert isinstance(repo_obj, dict)
                repo = str(repo_obj.get("full_name", ""))
                path = str(item.get("path", ""))
                sha = str(item.get("sha", ""))
                if repo_obj.get("fork"):
                    skips["fork"] += 1
                    continue
                if repo in seen_repos:
                    skips["repo_already_sampled"] += 1
                    continue
                if path.rsplit("/", 1)[-1] != stratum:
                    skips["not_exact_filename"] += 1
                    continue
                try:
                    meta = json.loads(gh(f"repos/{repo}"))
                    spdx = str((meta.get("license") or {}).get("spdx_id") or "NONE")
                    if spdx not in OSI_ALLOWLIST:
                        skips["licence_not_osi"] += 1
                        seen_repos.add(repo)
                        continue
                    blob_path = CACHE / f"{sha}.txt"
                    if blob_path.exists():
                        content = blob_path.read_bytes()
                    else:
                        content = fetch_blob(repo, sha)
                    if len(content) > MAX_BYTES:
                        skips["too_large"] += 1
                        continue
                    branch = str(meta.get("default_branch", "HEAD"))
                    commit = gh(
                        f"repos/{repo}/commits/{branch}", accept="application/vnd.github.sha"
                    ).strip()
                except (RuntimeError, ValueError) as exc:
                    print(f"skip {repo}/{path}: {exc}", file=sys.stderr)
                    skips["error"] += 1
                    continue
                blob_path.write_bytes(content)
                have += 1
                seen_repos.add(repo)
                prefix = stratum.lstrip(".").split(".")[0].upper()
                rows.append(
                    {
                        "file_id": f"{prefix}-{have:03d}",
                        "stratum": stratum,
                        "repo": repo,
                        "path": path,
                        "blob_sha": sha,
                        "commit_sha": commit,
                        "license": spdx,
                        "stars": str(meta.get("stargazers_count", 0)),
                        "bytes": str(len(content)),
                        "collected_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }
                )
                write_files(rows)
        strata_log[stratum] = {
            "collected": have,
            "results_examined": seen_results,
            "pages": page - 1,
            **skips,
        }
        print(f"{stratum}: {have} files ({strata_log[stratum]})", file=sys.stderr)
    log["strata"] = strata_log
    log["total_files"] = len(rows)
    (DATA / "collection_log.json").write_text(
        json.dumps(log, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(collect())
