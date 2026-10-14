"""`rulewarden compile`: instruction file → rule proposals + an honest report of what was not compiled."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from rulewarden.compile.extract import RuleLine, extract
from rulewarden.compile.templates import HEURISTIC_HINTS, TEMPLATES
from rulewarden.config import Config
from rulewarden.engine.fixtures import qualify_rule
from rulewarden.engine.loader import engine_context, prepare_rules
from rulewarden.engine.schema import parse_rule
from rulewarden.errors import SchemaError


@dataclass
class LineOutcome:
    lineno: int
    text: str
    status: str
    template: str = ""
    rule_ids: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class CompileResult:
    source: str
    rules: list[dict[str, Any]] = field(default_factory=list)
    lines: list[LineOutcome] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        c: dict[str, int] = {
            "compiled": 0,
            "heuristic-candidate": 0,
            "undecidable": 0,
            "rejected": 0,
        }
        for ln in self.lines:
            c[ln.status] += 1
        return c


def classify_uncompiled(text: str) -> str:
    return "heuristic-candidate" if HEURISTIC_HINTS.search(text) else "undecidable"


_CLAUSE_RE = re.compile(r"(?<=[.;!?])\s+(?=[A-Z`*])|;\s+")


def clauses(text: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_RE.split(text) if c.strip()]


def match_templates(line: RuleLine) -> tuple[str, list[dict[str, Any]]]:
    """All templates that match any clause of the line; each template contributes once."""
    ids: list[str] = []
    bodies: list[dict[str, Any]] = []
    titles: set[str] = set()
    for clause in clauses(line.text):
        for t in TEMPLATES:
            if t.id in ids:
                continue
            m = t.pattern.search(clause)
            if not m:
                continue
            built = [b for b in t.build(m, clause) if b["title"] not in titles]
            if built:
                ids.append(t.id)
                titles.update(b["title"] for b in built)
                bodies.extend(built)
    return "+".join(ids), bodies


def compile_text(text: str, source: str, cfg: Config, prefix: str = "C") -> CompileResult:
    res = CompileResult(source=source)
    ctx = engine_context(cfg)
    for line in extract(text):
        tid, bodies = match_templates(line)
        if not bodies:
            res.lines.append(LineOutcome(line.lineno, line.text, classify_uncompiled(line.text)))
            continue
        ids: list[str] = []
        problems: list[str] = []
        for k, body in enumerate(bodies, start=1):
            rid = f"{prefix}-L{line.lineno}" + (f"-{k}" if len(bodies) > 1 else "")
            rule_dict = {"id": rid, **body, "source": f"{source}:L{line.lineno}"}
            try:
                rule = parse_rule(rule_dict, source)
                (pr,) = prepare_rules([rule], ctx)
            except SchemaError as exc:
                problems.append(str(exc))
                continue
            failures = [o for o in qualify_rule(cfg, pr) if not o.ok]
            if failures:
                problems.append(f"{rid}: fixtures failed ({failures[0].detail})")
                continue
            res.rules.append(rule_dict)
            ids.append(rid)
        if ids:
            res.lines.append(LineOutcome(line.lineno, line.text, "compiled", tid, ids))
        else:
            res.lines.append(
                LineOutcome(line.lineno, line.text, "rejected", tid, [], "; ".join(problems))
            )
    return res


def compile_file(path: Path, cfg: Config, prefix: str = "C") -> CompileResult:
    rel = path.resolve()
    try:
        rel_s = rel.relative_to(cfg.root.resolve()).as_posix()
    except ValueError:
        rel_s = path.name
    return compile_text(path.read_text(encoding="utf-8", errors="replace"), rel_s, cfg, prefix)


def to_yaml(res: CompileResult) -> str:
    return yaml.safe_dump(
        {"version": 1, "rules": res.rules}, sort_keys=False, allow_unicode=True, width=120
    )


def report_text(res: CompileResult) -> str:
    c = res.counts()
    out = [
        f"{res.source}: {len(res.lines)} rule-like lines — {c['compiled']} compiled into {len(res.rules)} rules, "
        f"{c['heuristic-candidate']} heuristic candidates, {c['undecidable']} undecidable, {c['rejected']} rejected",
        "Lines NOT enforced by rulewarden (review these; they stay advisory text for the agent):",
    ]
    for ln in res.lines:
        if ln.status != "compiled":
            extra = f" [{ln.reason}]" if ln.reason else ""
            out.append(f"  L{ln.lineno:<4} {ln.status:<20} {ln.text[:100]}{extra}")
    return "\n".join(out) + "\n"
