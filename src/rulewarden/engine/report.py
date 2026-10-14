"""Findings and reports. The managed style implements alarm management (P7); 'flat' is the RQ4 ablation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from rulewarden.engine.schema import Severity

EXIT_PASS = 0
EXIT_BLOCK = 1
EXIT_ERROR = 3


@dataclass(frozen=True, order=True)
class Finding:
    rule_id: str
    severity: str
    decidability: str
    path: str
    line: int | None
    title: str
    fix: str
    detail: str = ""
    kind: str = "violation"

    @property
    def blocking(self) -> bool:
        return self.severity != Severity.ADVISORY.value and (
            self.decidability == "deterministic" or self.kind == "error"
        )

    def sort_key(self) -> tuple[int, str, int, str, str]:
        return (Severity(self.severity).rank, self.path, self.line or 0, self.rule_id, self.detail)

    def location(self) -> str:
        if not self.path:
            return ""
        return f"{self.path}:{self.line}" if self.line else self.path

    def render(self) -> str:
        what = self.title + (f" ({self.detail})" if self.detail else "")
        if self.kind == "unverifiable":
            what = f"could not verify: {self.detail or self.title}"
        loc = self.location()
        head = f"[{self.rule_id} {self.severity}]"
        return f"{head} {loc + ' ' if loc else ''}{what} — Fix: {self.fix}"


@dataclass
class Result:
    findings: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    deviations_applied: list[dict[str, object]] = field(default_factory=list)
    ruleset_sha256: str = ""
    diff_sha256: str = ""
    rules_evaluated: int = 0
    rules_not_evaluated: list[str] = field(default_factory=list)
    as_of: str | None = None
    outcomes: dict[str, str] = field(default_factory=dict)
    fatal: bool = False

    @property
    def counts(self) -> dict[str, int]:
        c = {"critical": 0, "required": 0, "advisory": 0}
        for f in dedupe(self.findings):
            c[f.severity] += 1
        return c

    @property
    def exit_code(self) -> int:
        if self.fatal or any(f.kind == "error" and f.blocking for f in self.findings):
            return EXIT_ERROR
        if any(f.blocking for f in self.findings):
            return EXIT_BLOCK
        return EXIT_PASS

    @property
    def status(self) -> str:
        return {EXIT_PASS: "pass", EXIT_BLOCK: "blocked", EXIT_ERROR: "error"}[self.exit_code]


def dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, int | None, str, str]] = set()
    out = []
    for f in findings:
        key = (f.rule_id, f.path, f.line, f.detail, f.kind)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def ordered(findings: list[Finding]) -> list[Finding]:
    return sorted(dedupe(findings), key=Finding.sort_key)


def to_json(result: Result) -> str:
    """Canonical JSON: sorted keys, stable finding order, no timestamps (determinism contract §5)."""
    payload: dict[str, object] = {
        "version": 1,
        "status": result.status,
        "exit_code": result.exit_code,
        "counts": result.counts,
        "findings": [asdict(f) for f in ordered(result.findings)],
        "errors": sorted(result.errors),
        "deviations_applied": sorted(
            result.deviations_applied, key=lambda d: json.dumps(d, sort_keys=True)
        ),
        "ruleset_sha256": result.ruleset_sha256,
        "diff_sha256": result.diff_sha256,
        "rules_evaluated": result.rules_evaluated,
        "rules_not_evaluated": sorted(result.rules_not_evaluated),
    }
    if result.as_of is not None:
        payload["as_of"] = result.as_of
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _header(result: Result, shown_adv: int, total_adv: int) -> str:
    c = result.counts
    if result.exit_code == EXIT_ERROR:
        lead = "ERROR — rulewarden could not verify this change; failing closed"
    elif result.exit_code == EXIT_BLOCK:
        lead = "BLOCKED"
    else:
        lead = "PASS"
    parts = [f"{c[s]} {s}" for s in ("critical", "required", "advisory") if c[s] or s == "advisory"]
    if not any(c.values()):
        return f"{lead} — no findings"
    tail = f" (showing {shown_adv})" if shown_adv < total_adv else ""
    return f"{lead} — {', '.join(parts)}{tail}"


def render_text(
    result: Result, style: str = "managed", advisory_cap: int = 5, max_chars: int = 2000
) -> str:
    if style == "flat":
        return render_flat(result)
    findings = ordered(result.findings)
    blocking = [f for f in findings if f.severity != "advisory"]
    advisory = [f for f in findings if f.severity == "advisory"]
    shown_adv = advisory[: max(advisory_cap, 0)]
    header = _header(result, len(shown_adv), len(advisory))
    lines = [header]
    budget = max_chars - len(header) - 1
    hidden = 0
    for f in blocking + shown_adv:
        text = f.render()
        if max_chars > 0 and len(text) + 1 > budget - 80:
            hidden += 1
            continue
        lines.append(text)
        budget -= len(text) + 1
    hidden_adv = len(advisory) - len(shown_adv)
    if hidden:
        lines.append(
            f"+{hidden} more finding(s) not shown (message cap) — run `rulewarden check` for the full list"
        )
    if hidden_adv:
        lines.append(f"+{hidden_adv} advisory not shown — run `rulewarden check --all`")
    return "\n".join(lines) + "\n"


def render_flat(result: Result) -> str:
    """Unprioritised list in evaluation order, no caps or dedupe (RQ4 ablation, condition D)."""
    lines = [f"{len(result.findings)} finding(s):"] if result.findings else ["No findings."]
    for f in result.findings:
        loc = f.location()
        lines.append(
            f"{loc + ': ' if loc else ''}{f.rule_id}: {f.title}{' (' + f.detail + ')' if f.detail else ''}. {f.fix}"
        )
    return "\n".join(lines) + "\n"
