"""RQ3 safety properties: determinism across processes, fail-closed under adversarial inputs (§5, §6.4)."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import git

from rulewarden.config import Config, Limits, load_config
from rulewarden.doctor import determinism_selftest
from rulewarden.engine import gitsrc
from rulewarden.engine.diff import Diff, synthesize_added
from rulewarden.engine.loader import RuleSet, engine_context, load_rule_text, prepare_rules
from rulewarden.engine.report import EXIT_BLOCK, EXIT_ERROR, to_json
from rulewarden.engine.runner import Request, run_check
from rulewarden.errors import SchemaError


def _cli(
    root: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    exe = str(Path(sys.executable).parent / "rulewarden")
    return subprocess.run(
        [exe, *args, "--root", str(root)],
        capture_output=True,
        env={**os.environ, **(env or {})},
        check=False,
    )


def test_report_identical_across_processes_and_environments(locked_repo: Path) -> None:
    (locked_repo / "src/pkg/mod.py").write_text(
        "def f(x):\n    # worth noting — ünïcode\n    print(x)\n"
    )
    (locked_repo / "tests/test_mod.py").write_text("x = 1\n")
    digests = set()
    for env in (
        {"TZ": "UTC", "LC_ALL": "C", "PYTHONHASHSEED": "1"},
        {"TZ": "Asia/Tokyo", "LC_ALL": "en_US.UTF-8", "PYTHONHASHSEED": "999"},
    ):
        p = _cli(locked_repo, "check", "--format", "json", "--no-audit", env=env)
        assert p.returncode == EXIT_BLOCK
        digests.add(hashlib.sha256(p.stdout).hexdigest())
    assert len(digests) == 1


def test_doctor_selftest() -> None:
    ok, msg = determinism_selftest()
    assert ok, msg


def test_redos_pattern_cannot_load(repo: Path) -> None:
    (repo / "rules/evil.yaml").write_text(
        "version: 1\nrules:\n  - id: E-1\n    title: evil\n    severity: required\n    decidability: deterministic\n"
        "    check: {engine: regex, pattern: '(a+)+$'}\n    message: m\n    fixtures: {fail: [a], pass: [b]}\n"
    )
    p = _cli(repo, "test-rules")
    assert p.returncode == 3 and b"ReDoS" in p.stderr


def test_polynomial_regex_is_killed_by_budget(tmp_path: Path) -> None:
    rules = (
        "version: 1\nrules:\n  - id: P-1\n    title: slow\n    severity: required\n    decidability: deterministic\n"
        "    check: {engine: regex, on: file, pattern: '(a|aa)*c'}\n    message: m\n    fixtures: {fail: [c], pass: [b]}\n"
    )
    cfg = Config(root=tmp_path, limits=Limits(total_budget_s=1.0, max_line_chars=10**6))
    rs = RuleSet(rules=prepare_rules(load_rule_text(rules, "t"), engine_context(cfg)), files=())
    diff = Diff(files=[synthesize_added("x.txt", "a" * 60 + "\n")], raw_sha256="d")
    t0 = time.monotonic()
    res = run_check(
        cfg, Request(diff=diff, use_lock=False, check_protected_drift=False), ruleset=rs
    )
    assert time.monotonic() - t0 < 10
    assert res.exit_code == EXIT_ERROR and res.findings[0].rule_id == "RW-BUDGET"


def test_oversized_inputs_fail_closed(locked_repo: Path) -> None:
    line = "x = 1  # " + "a" * 90 + "\n"
    payload = line * (50 * 1024 * 1024 // len(line))
    untracked = locked_repo / "src/pkg/big.py"
    untracked.write_text(payload)
    t0 = time.monotonic()
    p = _cli(locked_repo, "check", "--format", "json", "--no-audit")
    assert time.monotonic() - t0 < 60
    assert p.returncode == EXIT_BLOCK and b"unverifiable" in p.stdout
    untracked.unlink()
    tracked = locked_repo / "src/pkg/mod.py"
    tracked.write_text(payload)
    t0 = time.monotonic()
    p = _cli(locked_repo, "check", "--format", "json", "--no-audit")
    assert time.monotonic() - t0 < 60
    assert p.returncode == EXIT_ERROR and b"RW-DIFF" in p.stdout and b"larger than" in p.stdout


def test_long_line_is_unverifiable_not_ignored(locked_repo: Path) -> None:
    (locked_repo / "src/pkg/min.js").write_text("var a='" + "x" * 30000 + "';\n")
    (locked_repo / "rules/basic.yaml").write_text(
        (locked_repo / "rules/basic.yaml").read_text()
        + "  - id: T-007\n    title: no eval\n    severity: required\n"
        "    decidability: deterministic\n    applies_to: ['**/*.js']\n    check: {engine: regex, pattern: 'eval\\('}\n"
        "    message: m\n    fixtures: {fail: ['eval(x)'], pass: ['x']}\n"
    )
    cfg = load_config(locked_repo)
    res = run_check(cfg, Request(diff=gitsrc.worktree_diff(cfg), use_lock=False))
    t7 = [f for f in res.findings if f.rule_id == "T-007"]
    assert t7 and t7[0].kind == "unverifiable" and res.exit_code == EXIT_BLOCK


@pytest.mark.parametrize(
    "corruption",
    ["version: 1\nrules: [\n", "\x00\x01binary", "version: 1\nrules:\n  - id: X\n", ""],
)
def test_corrupted_rule_file_fails_closed(locked_repo: Path, corruption: str) -> None:
    (locked_repo / "rules/basic.yaml").write_text(corruption)
    p = _cli(locked_repo, "check", "--no-audit")
    assert p.returncode in (EXIT_BLOCK, EXIT_ERROR)
    assert b"RW-LOCK" in p.stdout or b"RW-LOAD" in p.stdout


def test_lockfile_tampering(locked_repo: Path) -> None:
    lock = locked_repo / "rules.lock"
    lock.write_text(lock.read_text().replace('"ruleset_sha256": "', '"ruleset_sha256": "0'))
    assert b"RW-LOCK" in _cli(locked_repo, "check", "--no-audit").stdout
    lock.write_text("{not json")
    assert b"RW-LOCK" in _cli(locked_repo, "check", "--no-audit").stdout
    lock.write_text('{"version": 9}')
    assert b"RW-LOCK" in _cli(locked_repo, "check", "--no-audit").stdout
    lock.write_text('{"version": 1}')
    assert b"RW-LOCK" in _cli(locked_repo, "check", "--no-audit").stdout


def test_protected_file_drift_detected_without_diff(locked_repo: Path, lock_fn) -> None:  # type: ignore[no-untyped-def]
    wf = locked_repo / ".github/workflows/ci.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text("on: push\n")
    lock_fn(locked_repo)
    git(locked_repo, "add", "-A")
    git(locked_repo, "commit", "-q", "-m", "wf")
    wf.write_text("on: never\n")
    cfg = load_config(locked_repo)
    res = run_check(cfg, Request(diff=Diff(files=[], raw_sha256="")))
    assert [f.rule_id for f in res.findings] == ["T-004"] and res.findings[
        0
    ].path == ".github/workflows/ci.yml"
    wf.unlink()
    res = run_check(cfg, Request(diff=Diff(files=[], raw_sha256="")))
    assert res.findings[0].detail.startswith("deleted")


def test_injected_engine_timeout_fails_closed(
    locked_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rulewarden.engine.checks import ast_check

    monkeypatch.setattr(ast_check, "run", lambda *a, **k: time.sleep(30))
    (locked_repo / "src/pkg/mod.py").write_text("x = 1\n")
    cfg = load_config(locked_repo)
    cfg = Config(**{**cfg.__dict__, "limits": Limits(total_budget_s=0.5)})
    res = run_check(cfg, Request(diff=gitsrc.worktree_diff(cfg)))
    assert res.exit_code == EXIT_ERROR and res.findings[0].rule_id == "RW-BUDGET"


def test_shell_bypass_attempts_on_protected_paths(locked_repo: Path) -> None:
    rules = Path(__file__).resolve().parents[1] / "src/rulewarden/packs/protected-set.yaml"
    cfg = Config(root=locked_repo)
    rs = RuleSet(
        rules=prepare_rules(load_rule_text(rules.read_text(), "p"), engine_context(cfg)), files=()
    )
    attempts = [
        "printf x >> rules/packs/voice.yaml",
        "python3 - <<'EOF' > rules.lock\nEOF",
        "cp /tmp/x .claude/settings.json",
        "mv evil.yml .github/workflows/ci.yml",
        "git restore --source=HEAD~3 rules/",
        "uv run rulewarden lock --ci",
        "git -c core.hooksPath=/dev/null commit -m x",
    ]
    for cmd in attempts:
        res = run_check(cfg, Request(command=cmd, use_lock=False), ruleset=rs)
        assert res.exit_code == EXIT_BLOCK, cmd


def test_json_stable_under_input_reordering(tmp_path: Path) -> None:
    rules = (
        "version: 1\nrules:\n  - id: A-1\n    title: t\n    severity: required\n    decidability: deterministic\n"
        "    check: {engine: regex, pattern: bad}\n    message: m\n    fixtures: {fail: [bad], pass: [ok]}\n"
    )
    cfg = Config(root=tmp_path)
    rs = RuleSet(rules=prepare_rules(load_rule_text(rules, "t"), engine_context(cfg)), files=())
    f1, f2 = synthesize_added("b.txt", "bad\n"), synthesize_added("a.txt", "bad\nbad\n")
    out1 = to_json(
        run_check(
            cfg,
            Request(diff=Diff([f1, f2], "h"), use_lock=False, check_protected_drift=False),
            ruleset=rs,
        )
    )
    out2 = to_json(
        run_check(
            cfg,
            Request(diff=Diff([f2, f1], "h"), use_lock=False, check_protected_drift=False),
            ruleset=rs,
        )
    )
    assert out1 == out2


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    rule = (
        "  - id: D-1\n    title: t\n    severity: advisory\n    decidability: deterministic\n"
        "    check: {engine: regex, pattern: x}\n    message: m\n    fixtures: {fail: [x], pass: [y]}\n"
    )
    with pytest.raises(SchemaError, match="duplicate"):
        prepare_rules(
            load_rule_text("version: 1\nrules:\n" + rule + rule, "t"),
            engine_context(Config(root=tmp_path)),
        )


KEY = "AKIA" + "IOSFODNN7EXAMPLE"
SECRET_RULE = """
version: 1
rules:
  - id: S-1
    title: AWS key
    severity: critical
    decidability: deterministic
    check: {engine: regex, pattern: 'AKIA[0-9A-Z]{16}'}
    message: Remove the key.
    fixtures: {fail: ["KEY_PLACEHOLDER"], pass: ["nothing"]}
""".replace("KEY_PLACEHOLDER", KEY)


def _secret_repo(repo: Path, lock_fn) -> Path:  # type: ignore[no-untyped-def]
    (repo / "rules/basic.yaml").write_text(SECRET_RULE)
    lock_fn(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "secret rule")
    return repo


@pytest.mark.parametrize(
    "payload",
    [
        b'k="' + KEY.encode() + b'"\n\x00',
        f'k="{KEY}"\n'.encode("utf-16"),
        f'k="{KEY}"\n'.encode("utf-16-le"),
        f'k="{KEY}"\n'.encode("utf-32"),
        f'k="{KEY}"\n'.encode("utf-32-le"),
        f'k="{KEY}"\n'.encode("utf-32-be"),
        b"\x89PNG\r\n\x1a\n\x00\x00" + KEY.encode() + b"\x00\xff",
    ],
)
def test_binary_looking_files_are_still_scanned(repo: Path, lock_fn, payload: bytes) -> None:  # type: ignore[no-untyped-def]
    root = _secret_repo(repo, lock_fn)
    (root / "src/pkg/leak.bin").write_bytes(payload)
    cfg = load_config(root)
    assert "S-1" in {
        f.rule_id for f in run_check(cfg, Request(diff=gitsrc.worktree_diff(cfg))).findings
    }
    git(root, "add", "src/pkg/leak.bin")
    assert "S-1" in {
        f.rule_id for f in run_check(cfg, Request(diff=gitsrc.staged_diff(cfg))).findings
    }
    git(root, "commit", "-q", "-m", "leak")
    rng = gitsrc.range_diff(cfg, "HEAD~1", "HEAD")
    res = run_check(cfg, Request(diff=rng, check_protected_drift=False))
    assert "S-1" in {f.rule_id for f in res.findings}


def test_clean_binary_file_passes(repo: Path, lock_fn) -> None:  # type: ignore[no-untyped-def]
    root = _secret_repo(repo, lock_fn)
    (root / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x01")
    cfg = load_config(root)
    assert run_check(cfg, Request(diff=gitsrc.worktree_diff(cfg))).findings == []
