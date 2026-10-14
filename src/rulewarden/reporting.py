"""Audit-log rendering (P9), near-miss statistics (P10) and framework evidence summaries (P12)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

from rulewarden.config import Config
from rulewarden.engine import audit
from rulewarden.errors import RulewardenError


def _entries(cfg: Config) -> list[dict[str, Any]]:
    return list(audit.read(cfg.root))


def render_audit(cfg: Config, fmt: str, limit: int) -> str:
    entries = _entries(cfg)
    intact, n, msg = audit.verify_chain(cfg.root)
    if fmt == "json":
        return (
            json.dumps(
                {
                    "chain": {"intact": intact, "entries": n, "message": msg},
                    "entries": entries[-limit:],
                },
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
    out = [
        "# rulewarden audit log",
        "",
        f"Entries: {len(entries)} · hash chain: {'intact' if intact else 'BROKEN — ' + msg}",
        "",
        "| time (UTC) | harness | event | status | critical | required | advisory | findings |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for e in entries[-limit:]:
        c = e.get("counts", {})
        out.append(
            f"| {str(e.get('ts', ''))[:19]} | {e.get('harness', '')} | {e.get('event', '')} | {e.get('status', '')} | "
            f"{c.get('critical', 0)} | {c.get('required', 0)} | {c.get('advisory', 0)} | {', '.join(e.get('findings', []))} |"
        )
    return "\n".join(out) + "\n"


def compute_stats(cfg: Config) -> dict[str, Any]:
    entries = _entries(cfg)
    fires: Counter[str] = Counter()
    by_event: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    prevented = 0
    for e in entries:
        by_event[f"{e.get('harness')}:{str(e.get('event', '')).split(':')[0]}"] += 1
        by_status[str(e.get("status"))] += 1
        for rid, outcome in (e.get("outcomes") or {}).items():
            if outcome == "fail":
                fires[rid] += 1
        if e.get("status") != "pass" and str(e.get("event", "")).startswith("PreToolUse"):
            prevented += 1
        sessions[str(e.get("session_id") or "")].append(e)
    cycles: list[int] = []
    for sid, evs in sessions.items():
        if not sid:
            continue
        run = 0
        for e in evs:
            if e.get("status") == "pass":
                if run:
                    cycles.append(run)
                run = 0
            else:
                run += 1
    try:
        from rulewarden.engine.loader import load_rules

        known = sorted(pr.rule.id for pr in load_rules(cfg).rules if pr.rule.check is not None)
    except RulewardenError:
        known = []
    return {
        "entries": len(entries),
        "by_event": dict(sorted(by_event.items())),
        "by_status": dict(sorted(by_status.items())),
        "prevented_before_actuation": prevented,
        "rule_fires": dict(sorted(fires.items(), key=lambda kv: (-kv[1], kv[0]))),
        "never_fired": [r for r in known if r not in fires],
        "self_correction": {
            "episodes": len(cycles),
            "mean_blocks_before_clean": round(sum(cycles) / len(cycles), 3) if cycles else None,
            "max_blocks_before_clean": max(cycles) if cycles else None,
        },
    }


def render_stats(s: dict[str, Any]) -> str:
    out = [
        f"audit entries: {s['entries']}  ({', '.join(f'{k}={v}' for k, v in s['by_status'].items())})",
        f"prevented before actuation (PreToolUse denials): {s['prevented_before_actuation']}",
    ]
    sc = s["self_correction"]
    out.append(
        f"self-correction episodes: {sc['episodes']}, mean blocks before clean: {sc['mean_blocks_before_clean']}"
    )
    out.append(
        "rule fires: " + (", ".join(f"{k}×{v}" for k, v in s["rule_fires"].items()) or "none")
    )
    out.append(
        f"never fired ({len(s['never_fired'])}; review candidates): " + ", ".join(s["never_fired"])
    )
    return "\n".join(out) + "\n"


NIST_MAP = (
    (
        "GOVERN 1",
        "Policies, processes and procedures are in place",
        "rules/ with traceable `source:` lines; rules.lock signed off by a human",
    ),
    (
        "MAP 1",
        "Context is established and understood",
        "`rulewarden compile` report: which instruction lines are enforced, heuristic or undecidable",
    ),
    (
        "MEASURE 2",
        "AI systems are evaluated for trustworthy characteristics",
        "`test-rules` fixture qualification; determinism self-test (`doctor`)",
    ),
    (
        "MEASURE 3",
        "Mechanisms for tracking identified risks over time",
        "hash-chained audit log; `rulewarden stats` near-miss metrics",
    ),
    (
        "MANAGE 2",
        "Strategies to maximize benefits and minimize negative impacts",
        "fail-closed blocking of required/critical violations; deviations with approvers and expiry",
    ),
    (
        "MANAGE 4",
        "Risk treatments, including response and recovery, are documented and monitored",
        "deviation registry in rules.lock; audit log per session",
    ),
)


def framework_summary(cfg: Config, framework: str, fmt: str) -> str:
    s = compute_stats(cfg)
    intact, n, _ = audit.verify_chain(cfg.root)
    evidence = {"audit_entries": n, "audit_chain_intact": intact, "stats": s}
    rows = [{"function": f, "outcome": o, "rulewarden_evidence": ev} for f, o, ev in NIST_MAP]
    if fmt == "json":
        return (
            json.dumps(
                {"framework": framework, "mapping": rows, "evidence": evidence},
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
    out = [
        f"# Evidence summary — {framework}",
        "",
        "Mapping of rulewarden artefacts to NIST AI RMF 1.0 functions. This is evidence for a human assessor; "
        "it is not a conformity claim.",
        "",
        "| Function | Outcome | rulewarden evidence |",
        "|---|---|---|",
    ]
    out.extend(f"| {r['function']} | {r['outcome']} | {r['rulewarden_evidence']} |" for r in rows)
    out += [
        "",
        f"Audit entries: {n} (chain {'intact' if intact else 'broken'}); "
        f"blocked/error runs: {sum(v for k, v in s['by_status'].items() if k != 'pass')}.",
    ]
    return "\n".join(out) + "\n"
