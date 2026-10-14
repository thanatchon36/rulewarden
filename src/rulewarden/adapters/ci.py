"""CI adapter: check BASE...HEAD and emit GitHub Actions annotations next to the text report."""

from __future__ import annotations

from rulewarden.config import Config
from rulewarden.engine import gitsrc
from rulewarden.engine.report import Result, ordered
from rulewarden.engine.runner import Request, _synthetic, run_check
from rulewarden.errors import RulewardenError


def _escape(s: str) -> str:
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def gh_annotations(result: Result) -> list[str]:
    out = []
    for f in ordered(result.findings):
        level = "error" if f.blocking else "warning"
        loc = ""
        if f.path and not f.path.startswith(":"):
            loc = f" file={f.path}" + (f",line={f.line}" if f.line else "")
        title = f"{f.rule_id} {f.severity}"
        out.append(
            f"::{level}{loc},title={_escape(title)}::{_escape(f.render())}"
            if loc
            else f"::{level} title={_escape(title)}::{_escape(f.render())}"
        )
    return out


def check_range(cfg: Config, base: str, head: str = "HEAD") -> Result:
    try:
        diff = gitsrc.range_diff(cfg, base, head)
    except RulewardenError as exc:
        res = Result(fatal=True)
        res.findings.append(
            _synthetic(
                "RW-DIFF",
                "critical",
                "change could not be read",
                "fetch the base branch (actions/checkout fetch-depth: 0)",
                detail=str(exc)[:300],
                kind="error",
            )
        )
        return res
    return run_check(cfg, Request(diff=diff, check_protected_drift=False))
