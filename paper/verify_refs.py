"""Citation integrity (MISSION §7): resolve every bib entry and match its title.

Each entry in refs.bib must carry a `doi`, an `eprint` (arXiv id) or a `url`. The
resolved title must match the bib title. Results go to refs_verified.json; entries
that fail are written out of refs.verified.bib, and build.sh refuses to cite them.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
UA = "rulewarden-refcheck/0.1 (mailto:noreply@github.com)"
MATCH_THRESHOLD = 0.8


@dataclass
class Entry:
    key: str
    kind: str
    fields: dict[str, str]
    raw: str


def parse_bib(text: str) -> list[Entry]:
    entries: list[Entry] = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        start = m.start()
        depth = 0
        i = text.index("{", start)
        for j in range(i, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
        raw = text[start : j + 1]
        body = text[m.end() : j]
        fields: dict[str, str] = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}", body):
            fields[fm.group(1).lower()] = re.sub(r"\s+", " ", fm.group(2)).strip()
        entries.append(Entry(m.group(2), m.group(1).lower(), fields, raw))
    return entries


def norm_tokens(s: str) -> list[str]:
    s = html.unescape(s)
    s = re.sub(r"[{}\\]", "", s).lower()
    return re.findall(r"[a-z0-9]+", s)


def title_score(expected: str, found: str) -> float:
    a, b = norm_tokens(expected), norm_tokens(found)
    if not a or not b:
        return 0.0
    sa = set(a)
    return len(sa & set(b)) / len(sa)


def fetch(url: str, accept: str = "*/*") -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data: bytes = resp.read(3_000_000)
        return data.decode("utf-8", errors="replace")


def resolve_doi(doi: str) -> str:
    data = json.loads(fetch("https://api.crossref.org/works/" + urllib.parse.quote(doi)))
    titles = data["message"].get("title") or []
    subtitle = data["message"].get("subtitle") or []
    return " ".join(titles + subtitle)


def resolve_arxiv(eprint: str) -> str:
    xml = fetch("https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(eprint))
    entry = xml.split("<entry>", 1)
    if len(entry) < 2:
        raise LookupError("arXiv id not found")
    m = re.search(r"<title>(.*?)</title>", entry[1], re.S)
    if not m:
        raise LookupError("arXiv entry without title")
    return m.group(1)


def resolve_url(url: str, expected: str) -> str:
    page = fetch(url)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    toks = norm_tokens(text)
    want = norm_tokens(expected)
    # Return the best window of page text so the score reflects the title's presence.
    n = len(want)
    best = ""
    best_score = -1.0
    for i in range(0, max(1, len(toks) - n + 1)):
        window = " ".join(toks[i : i + n + 4])
        sc = title_score(expected, window)
        if sc > best_score:
            best, best_score = window, sc
            if sc >= 1.0:
                break
    return best


def verify(entry: Entry) -> dict[str, object]:
    f = entry.fields
    expected = f.get("title", "")
    record: dict[str, object] = {"key": entry.key, "title": expected}
    attempts: list[tuple[str, str]] = []
    if "doi" in f:
        attempts.append(("doi", f["doi"]))
    if "eprint" in f:
        attempts.append(("arxiv", f["eprint"]))
    if "url" in f:
        attempts.append(("url", f["url"]))
    if not attempts:
        record.update(status="unresolvable", reason="no doi/eprint/url")
        return record
    errors: list[str] = []
    for method, ident in attempts:
        try:
            if method == "doi":
                found = resolve_doi(ident)
            elif method == "arxiv":
                found = resolve_arxiv(ident)
            else:
                found = resolve_url(ident, expected)
        except (urllib.error.URLError, LookupError, KeyError, ValueError, TimeoutError) as exc:
            errors.append(f"{method}:{ident}: {exc}")
            continue
        score = title_score(expected, found)
        if score >= MATCH_THRESHOLD:
            record.update(
                status="verified",
                method=method,
                identifier=ident,
                resolved_title=re.sub(r"\s+", " ", found).strip()[:300],
                score=round(score, 3),
            )
            return record
        errors.append(f"{method}:{ident}: title mismatch ({score:.2f}): {found[:120]!r}")
        time.sleep(0.5)
    record.update(status="unresolvable", reason="; ".join(errors))
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bib", default=str(HERE / "refs.bib"))
    ap.add_argument("--out", default=str(HERE / "refs_verified.json"))
    ap.add_argument("--verified-bib", default=str(HERE / "refs.verified.bib"))
    args = ap.parse_args()
    entries = parse_bib(Path(args.bib).read_text(encoding="utf-8"))
    results = []
    for e in entries:
        r = verify(e)
        results.append(r)
        print(f"{r['status']:12} {e.key}", file=sys.stderr)
    ok = {r["key"] for r in results if r["status"] == "verified"}
    out = {
        "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "threshold": MATCH_THRESHOLD,
        "entries": results,
    }
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    kept = [e.raw for e in entries if e.key in ok]
    Path(args.verified_bib).write_text("\n\n".join(kept) + "\n", encoding="utf-8")
    bad = [r["key"] for r in results if r["status"] != "verified"]
    print(f"verified {len(ok)}/{len(entries)}; dropped: {', '.join(map(str, bad)) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
