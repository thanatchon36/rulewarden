"""Tool qualification (P6): every rule's failing fixtures must fire and passing fixtures must not."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from rulewarden.config import Config
from rulewarden.engine.diff import Diff, FileChange, diff_between, synthesize_added
from rulewarden.engine.globs import selected
from rulewarden.engine.loader import PreparedRule, RuleSet
from rulewarden.engine.runner import Request, _evaluate
from rulewarden.engine.schema import On, Rule, Scope
from rulewarden.errors import SchemaError


def default_path(rule: Rule) -> str:
    """A concrete path that satisfies the rule's first applies_to glob."""
    pat = rule.applies_to[0] if rule.applies_to else "**"
    path = (
        pat.replace("**/", "")
        .replace("**", "fixture.txt")
        .replace("*", "fixture")
        .replace("?", "x")
    )
    path = path.replace("[", "").replace("]", "").replace("!", "")
    if not path or path.endswith("/"):
        path += "fixture.txt"
    return path


@dataclass
class FixtureOutcome:
    rule_id: str
    expected: str
    index: int
    ok: bool
    detail: str = ""


@dataclass
class QualificationReport:
    outcomes: list[FixtureOutcome] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(o.ok for o in self.outcomes)

    @property
    def failures(self) -> list[FixtureOutcome]:
        return [o for o in self.outcomes if not o.ok]

    def summary(self) -> dict[str, object]:
        return {
            "rules": len({o.rule_id for o in self.outcomes}),
            "fixtures": len(self.outcomes),
            "passed": self.passed,
        }


def build_request(rule: Rule, fixture: Any) -> Request:
    assert rule.check is not None
    if rule.scope is Scope.COMMAND:
        cmd = fixture["command"] if isinstance(fixture, Mapping) else fixture
        if not isinstance(cmd, str):
            raise SchemaError(f"{rule.id}: command fixtures must be strings")
        return Request(command=cmd, use_lock=False, check_protected_drift=False)
    if rule.check.on is On.PATH:
        if isinstance(fixture, Mapping):
            path, status = str(fixture.get("path", "")), str(fixture.get("status", "modified"))
        else:
            path, status = str(fixture), "modified"
        if not path:
            raise SchemaError(f"{rule.id}: path fixtures need a path")
        files = [FileChange(path=path, status=status), *_companions(fixture)]
        return Request(
            diff=Diff(files=files, raw_sha256=""), use_lock=False, check_protected_drift=False
        )
    if isinstance(fixture, Mapping):
        path = str(fixture.get("path") or default_path(rule))
        content = fixture.get("content", "")
        before = fixture.get("before")
        if not isinstance(content, str) or (before is not None and not isinstance(before, str)):
            raise SchemaError(f"{rule.id}: fixture content/before must be strings")
        fc = (
            diff_between(path, before, content)
            if before is not None
            else synthesize_added(path, content)
        )
    elif isinstance(fixture, str):
        path = default_path(rule)
        fc = synthesize_added(path, fixture if fixture.endswith("\n") else fixture + "\n")
    else:
        raise SchemaError(f"{rule.id}: a fixture must be a string or a mapping")
    if not selected(fc.path, rule.applies_to, rule.exclude):
        raise SchemaError(
            f"{rule.id}: fixture path {fc.path!r} is not selected by applies_to; give an explicit path"
        )
    return Request(
        diff=Diff(files=[fc, *_companions(fixture)], raw_sha256=""),
        use_lock=False,
        check_protected_drift=False,
    )


def _companions(fixture: Any) -> list[FileChange]:
    """Extra changed paths for rules with unless_changed (fixture key `also_changed`)."""
    if not isinstance(fixture, Mapping):
        return []
    extra = fixture.get("also_changed", [])
    if not isinstance(extra, list) or not all(isinstance(e, str) for e in extra):
        raise SchemaError("fixture also_changed must be a list of paths")
    return [FileChange(path=e, status="modified") for e in extra]


def qualify_rule(config: Config, pr: PreparedRule) -> list[FixtureOutcome]:
    rule = pr.rule
    if rule.fixtures is None:
        return []
    single = RuleSet(rules=(pr,), files=())
    out: list[FixtureOutcome] = []
    for expected, items in (("fail", rule.fixtures.fail), ("pass", rule.fixtures.pass_)):
        for i, fx in enumerate(items):
            try:
                res = _evaluate(config, single, build_request(rule, fx), lock=None)
            except SchemaError as exc:
                out.append(FixtureOutcome(rule.id, expected, i, False, str(exc)))
                continue
            mine = [f for f in res.findings if f.rule_id == rule.id]
            if res.errors:
                out.append(FixtureOutcome(rule.id, expected, i, False, "; ".join(res.errors)))
            elif expected == "fail":
                fired = any(f.kind == "violation" for f in mine)
                out.append(
                    FixtureOutcome(
                        rule.id, expected, i, fired, "" if fired else "rule did not fire"
                    )
                )
            else:
                ok = not mine
                out.append(FixtureOutcome(rule.id, expected, i, ok, "" if ok else mine[0].render()))
    return out


def qualify(config: Config, ruleset: RuleSet) -> QualificationReport:
    rep = QualificationReport()
    for pr in ruleset.rules:
        rep.outcomes.extend(qualify_rule(config, pr))
    return rep
