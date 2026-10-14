"""Evaluate a rule set against a change (diff and/or command). No network, no model, no randomness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from rulewarden.config import Config, load_approvers
from rulewarden.engine import deviations as dev
from rulewarden.engine.bounded import run_bounded
from rulewarden.engine.checks import EngineContext, Hit, Target, engine
from rulewarden.engine.checks import glob_check as globc
from rulewarden.engine.diff import Diff, FileChange
from rulewarden.engine.globs import selected
from rulewarden.engine.loader import PreparedRule, RuleSet, engine_context, load_rules
from rulewarden.engine.lock import Lock, protected_files, verify_lock
from rulewarden.engine.report import Finding, Result
from rulewarden.engine.schema import Decidability, EngineName, On, Scope
from rulewarden.errors import (
    BudgetExceeded,
    EngineError,
    LoadError,
    LockError,
    RulewardenError,
    SchemaError,
)

COMMAND_PATH = ":command"


@dataclass(frozen=True)
class Request:
    diff: Diff | None = None
    command: str | None = None
    as_of: date | None = None
    use_lock: bool = True
    check_protected_drift: bool = True


def today_utc() -> date:
    return datetime.now(UTC).date()


def _target(fc: FileChange, changeset: tuple[str, ...] = ()) -> Target:
    return Target(
        path=fc.path,
        status=fc.status,
        content=fc.new_content,
        added=fc.added,
        blocks=fc.blocks,
        changeset=changeset,
    )


def _finding(pr: PreparedRule, path: str, hit: Hit, kind: str | None = None) -> Finding:
    r = pr.rule
    return Finding(
        rule_id=r.id,
        severity=r.severity.value,
        decidability=r.decidability.value,
        path=path,
        line=hit.line,
        title=r.title,
        fix=r.message.strip(),
        detail=hit.detail,
        kind=kind or ("unverifiable" if hit.unverifiable else "violation"),
    )


def _synthetic(
    rule_id: str,
    severity: str,
    title: str,
    fix: str,
    path: str = "",
    line: int | None = None,
    detail: str = "",
    kind: str = "violation",
) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        decidability="deterministic",
        path=path,
        line=line,
        title=title,
        fix=fix,
        detail=detail,
        kind=kind,
    )


def _hits_for_file(
    pr: PreparedRule, fc: FileChange, ctx: EngineContext, changeset: tuple[str, ...] = ()
) -> list[Hit]:
    r = pr.rule
    assert r.check is not None
    on = r.check.on
    mod = engine(r.check.engine)
    if on is On.PATH:
        return list(mod.run(pr.prepared, on, _target(fc, changeset), ctx))
    if fc.status == "deleted" or (fc.binary and not fc.too_large):
        return []
    if fc.too_large and on in (On.FILE, On.HUNKS, On.ADDED_LINES):
        return [Hit(None, "file too large to verify", True)]
    hits = list(mod.run(pr.prepared, on, _target(fc, changeset), ctx))
    if r.scope is Scope.DIFF and on is On.FILE:
        added = fc.added_line_numbers
        hits = [h for h in hits if h.line is None or h.line in added or h.unverifiable]
    return hits


def _protected_drift(config: Config, lock: Lock, diff_paths: set[str]) -> list[FileChange]:
    """Protected files whose current content differs from the lock but are not in the diff."""
    current = protected_files(config)
    out: list[FileChange] = []
    for path in sorted(set(current) | set(lock.protected)):
        if path in diff_paths or current.get(path) == lock.protected.get(path):
            continue
        status = (
            "added"
            if path not in lock.protected
            else ("deleted" if path not in current else "modified")
        )
        out.append(FileChange(path=path, status=status))
    return out


def _locked_ok(config: Config, lock: Lock | None, fc: FileChange) -> bool:
    """True if a protected path's (proposed) content is exactly what a human locked."""
    import hashlib

    from rulewarden.engine.lock import _hash

    if lock is None:
        return False
    disk = _hash(config.root / fc.path)
    if fc.status == "deleted":
        current = None
    elif fc.new_content is not None:
        current = hashlib.sha256(fc.new_content.encode("utf-8", "surrogateescape")).hexdigest()
    else:
        current = disk
    if fc.path == config.lock_file:
        # rules.lock was already verified against the rules; accept it only as it is on disk.
        return current is not None and current == disk
    return lock.protected.get(fc.path) == current


def _locked_rule_input(lock: Lock | None, fc: FileChange) -> bool:
    """True if this file is a rule input whose content is exactly what a human locked.

    Rule files contain their own failing fixtures, so content rules would flag them;
    their integrity is already guaranteed by the lock (ADR-012).
    """
    import hashlib

    if lock is None or fc.path not in lock.rules or fc.new_content is None:
        return False
    current = hashlib.sha256(fc.new_content.encode("utf-8", "surrogateescape")).hexdigest()
    return lock.rules[fc.path] == current


def _evaluate(config: Config, ruleset: RuleSet, req: Request, lock: Lock | None) -> Result:
    ctx = engine_context(config)
    res = Result()
    files = list(req.diff.files) if req.diff else []
    changeset = tuple(sorted({f.path for f in files} | {f.old_path for f in files if f.old_path}))
    drift: list[FileChange] = []
    if lock is not None and req.check_protected_drift and req.diff is not None:
        drift = _protected_drift(config, lock, {f.path for f in files})
    approvers = load_approvers(config.root)
    as_of = req.as_of or today_utc()
    used_expiry = False
    devs_by_path: dict[str, list[dev.Deviation]] = {}
    for fc in files:
        if fc.new_content is not None:
            devs_by_path[fc.path] = dev.scan(fc.path, fc.new_content)

    for pr in ruleset.rules:
        r = pr.rule
        if r.decidability is Decidability.UNDECIDABLE or r.check is None:
            res.rules_not_evaluated.append(r.id)
            continue
        res.rules_evaluated += 1
        found: list[Finding] = []
        try:
            if r.scope is Scope.COMMAND:
                if req.command is not None:
                    hits = engine(r.check.engine).run(
                        pr.prepared, r.check.on, Target(COMMAND_PATH, command=req.command), ctx
                    )
                    found.extend(_finding(pr, COMMAND_PATH, h) for h in hits)
            else:
                exempt = (
                    r.check.engine is EngineName.GLOB
                    and isinstance(pr.prepared, globc.Prepared)
                    and pr.prepared.exempt_if_locked
                )
                candidates = files + (drift if exempt else [])
                for fc in candidates:
                    if not selected(fc.path, r.applies_to, r.exclude):
                        continue
                    if exempt and _locked_ok(config, lock, fc):
                        continue
                    if r.check.engine is not EngineName.GLOB and _locked_rule_input(lock, fc):
                        continue
                    for h in _hits_for_file(pr, fc, ctx, changeset):
                        found.append(_finding(pr, fc.path, h))
        except (EngineError, OSError, ValueError) as exc:
            msg = f"{r.id}: {exc}"
            res.errors.append(msg)
            res.outcomes[r.id] = "error"
            if r.severity.blocking:
                found = [
                    _synthetic(
                        r.id,
                        r.severity.value,
                        r.title,
                        "fix the rule or its engine; failing closed",
                        detail=str(exc)[:200],
                        kind="error",
                    )
                ]
            else:
                found = []
        kept: list[Finding] = []
        for f in found:
            d = (
                dev.covering(devs_by_path.get(f.path, []), f.rule_id, f.line)
                if f.kind == "violation"
                else None
            )
            if d is None:
                kept.append(f)
                continue
            if d.expires is not None:
                used_expiry = True
            verdict = _deviation_verdict(d, pr, approvers, lock, as_of)
            if verdict == "ok":
                res.deviations_applied.append(
                    {
                        "rule": d.rule_id,
                        "path": d.path,
                        "line": d.line,
                        "approved_by": d.approved_by,
                        "reason": d.reason,
                    }
                )
            else:
                kept.append(
                    Finding(
                        **{
                            **f.__dict__,
                            "detail": (f.detail + "; " if f.detail else "")
                            + f"deviation rejected: {verdict}",
                        }
                    )
                )
        res.findings.extend(kept)
        res.outcomes.setdefault(
            r.id,
            "fail" if any(k.kind != "error" for k in kept) else ("deviated" if found else "pass"),
        )

    res.findings.extend(_unregistered_deviations(files, ruleset, lock, devs_by_path))
    if used_expiry:
        res.as_of = as_of.isoformat()
    return res


def _deviation_verdict(
    d: dev.Deviation, pr: PreparedRule, approvers: frozenset[str], lock: Lock | None, as_of: date
) -> str:
    if d.malformed:
        return d.malformed
    if not pr.rule.deviations_allowed:
        return f"deviations are forbidden for {pr.rule.id}"
    if d.expires is not None and d.expires < as_of:
        return f"expired {d.expires.isoformat()}"
    if d.approved_by not in approvers:
        return f"approver {d.approved_by!r} is not listed in .rulewarden/approvers"
    if pr.rule.severity.blocking and (lock is None or d.fingerprint not in lock.deviations):
        return (
            "deviations of required/critical rules must be registered by a human `rulewarden lock`"
        )
    return "ok"


def _unregistered_deviations(
    files: list[FileChange],
    ruleset: RuleSet,
    lock: Lock | None,
    devs_by_path: dict[str, list[dev.Deviation]],
) -> list[Finding]:
    """An added deviation of a required/critical rule that no human registered is itself critical (P8)."""
    blocking = {pr.rule.id for pr in ruleset.rules if pr.rule.severity.blocking}
    out = []
    for fc in files:
        added = fc.added_line_numbers
        for d in devs_by_path.get(fc.path, []):
            if (
                d.line in added
                and d.rule_id in blocking
                and (lock is None or d.fingerprint not in lock.deviations)
            ):
                out.append(
                    _synthetic(
                        "RW-DEVIATION",
                        "critical",
                        f"unapproved deviation of {d.rule_id} added",
                        "remove the deviation comment and fix the violation; only a human can approve deviations of required rules",
                        path=fc.path,
                        line=d.line,
                    )
                )
    return out


def run_check(
    config: Config, req: Request, ruleset: RuleSet | None = None, bounded: bool = True
) -> Result:
    """Load (unless given), verify the lock, and evaluate within the total budget. Never raises."""
    try:
        lock = None
        if req.use_lock:
            lock = verify_lock(config)
        rs = ruleset if ruleset is not None else load_rules(config)
    except LockError as exc:
        res = Result(fatal=False)
        res.findings.append(
            _synthetic(
                "RW-LOCK",
                "critical",
                "rule set is not locked by a human",
                "a human must review the rule change and run `rulewarden lock`",
                detail=str(exc),
            )
        )
        return res
    except (LoadError, SchemaError, RulewardenError, OSError) as exc:
        res = Result(fatal=True)
        res.errors.append(str(exc))
        res.findings.append(
            _synthetic(
                "RW-LOAD",
                "critical",
                "rules could not be loaded",
                "fix the rule files; failing closed",
                detail=str(exc)[:300],
                kind="error",
            )
        )
        return res
    try:
        result = run_bounded(
            lambda: _evaluate(config, rs, req, lock),
            config.limits.total_budget_s if bounded else None,
        )
    except (BudgetExceeded, EngineError) as exc:
        result = Result(fatal=True)
        result.errors.append(str(exc))
        result.findings.append(
            _synthetic(
                "RW-BUDGET",
                "critical",
                "evaluation did not complete",
                "reduce the change size or fix the slow rule; failing closed",
                detail=str(exc)[:300],
                kind="error",
            )
        )
    result.ruleset_sha256 = lock.ruleset_sha256 if lock else rs.digest
    result.diff_sha256 = req.diff.raw_sha256 if req.diff else ""
    if req.command is not None:
        import hashlib

        result.diff_sha256 = hashlib.sha256(("command\0" + req.command).encode("utf-8")).hexdigest()
    return result
