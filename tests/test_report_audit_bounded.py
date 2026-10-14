from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from rulewarden.engine import audit
from rulewarden.engine.bounded import run_bounded
from rulewarden.engine.report import Finding, Result, dedupe, render_flat, render_text, to_json
from rulewarden.errors import BudgetExceeded, EngineError


def mk(rule: str, sev: str, path: str = "a.py", line: int | None = 1, **kw: str) -> Finding:
    return Finding(
        rule_id=rule,
        severity=sev,
        decidability=kw.get("dec", "deterministic"),
        path=path,
        line=line,
        title=f"title {rule}",
        fix=f"fix {rule}",
        detail=kw.get("detail", ""),
        kind=kw.get("kind", "violation"),
    )


def test_managed_report_orders_caps_and_dedupes() -> None:
    res = Result(
        findings=[mk(f"A-{i}", "advisory", line=i) for i in range(8)]
        + [mk("C-1", "critical"), mk("R-1", "required"), mk("R-1", "required")]
    )
    text = render_text(res, advisory_cap=5, max_chars=2000)
    lines = text.splitlines()
    assert lines[0] == "BLOCKED — 1 critical, 1 required, 8 advisory (showing 5)"
    assert lines[1].startswith("[C-1 critical]") and lines[2].startswith("[R-1 required]")
    assert sum(1 for ln in lines if ln.startswith("[A-")) == 5
    assert lines[-1].startswith("+3 advisory not shown")
    assert len(dedupe(res.findings)) == 10


def test_report_char_cap() -> None:
    res = Result(findings=[mk(f"R-{i}", "required", detail="x" * 150) for i in range(30)])
    text = render_text(res, max_chars=1000)
    assert len(text) <= 1100 and "not shown (message cap)" in text
    assert len(render_text(res, max_chars=0)) > 3000


def test_pass_and_empty_headers() -> None:
    assert render_text(Result()) == "PASS — no findings\n"
    assert (
        render_text(Result(findings=[mk("A-1", "advisory")])).startswith("PASS — 0 critical")
        is False
    )
    assert render_text(Result(findings=[mk("A-1", "advisory")])).startswith("PASS — 1 advisory")


def test_flat_report_is_unordered_and_uncapped() -> None:
    fs = [mk("A-1", "advisory"), mk("C-1", "critical", path="", line=None), mk("A-1", "advisory")]
    text = render_flat(Result(findings=fs))
    assert text.splitlines()[0] == "3 finding(s):" and "A-1" in text.splitlines()[1]
    assert render_text(Result(findings=fs), style="flat") == text
    assert render_flat(Result()) == "No findings.\n"


def test_json_is_canonical() -> None:
    res = Result(
        findings=[mk("R-1", "required"), mk("C-1", "critical")], ruleset_sha256="r", diff_sha256="d"
    )
    a, b = (
        to_json(res),
        to_json(Result(findings=list(reversed(res.findings)), ruleset_sha256="r", diff_sha256="d")),
    )
    assert a == b
    data = json.loads(a)
    assert (
        data["status"] == "blocked"
        and data["findings"][0]["rule_id"] == "C-1"
        and "as_of" not in data
    )


def test_finding_render_variants() -> None:
    assert mk("R", "required", path="", line=None).render().startswith("[R required] title R")
    assert "could not verify" in mk("R", "required", kind="unverifiable", detail="too big").render()
    assert mk("R", "required", path="x.py", line=None).location() == "x.py"
    assert mk("H", "advisory", dec="heuristic").blocking is False


def test_audit_chain(tmp_path: Path) -> None:
    for i in range(3):
        audit.append(
            tmp_path,
            Result(findings=[mk("R-1", "required")] if i else []),
            audit.Event("cli", "check", "s", i, note="n"),
        )
    entries = list(audit.read(tmp_path))
    assert (
        len(entries) == 3
        and entries[0]["prev"] == audit.GENESIS
        and entries[1]["status"] == "blocked"
    )
    assert audit.verify_chain(tmp_path) == (True, 3, "intact")
    log = tmp_path / ".rulewarden/audit.jsonl"
    lines = log.read_text().splitlines()
    log.write_text("\n".join([lines[0], lines[2]]) + "\n")
    ok, _, msg = audit.verify_chain(tmp_path)
    assert not ok and "chain broken" in msg
    log.write_text("not json\n")
    assert audit.verify_chain(tmp_path)[0] is False
    assert audit.verify_chain(tmp_path / "nowhere") == (True, 0, "no audit log")
    assert list(audit.read(tmp_path / "nowhere")) == []


def test_bounded_success_timeout_crash() -> None:
    assert run_bounded(lambda: 41 + 1, 5.0) == 42
    assert run_bounded(lambda: "in-process", None) == "in-process"
    t0 = time.monotonic()
    with pytest.raises(BudgetExceeded):
        run_bounded(lambda: time.sleep(10), 0.3)
    assert time.monotonic() - t0 < 5
    with pytest.raises(EngineError, match="ZeroDivisionError"):
        run_bounded(lambda: 1 / 0, 5.0)
    with pytest.raises(EngineError, match="died"):
        run_bounded(lambda: os._exit(9), 5.0)
    big = run_bounded(lambda: "x" * 2_000_000, 10.0)
    assert len(big) == 2_000_000
