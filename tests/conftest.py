from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from rulewarden.config import Config, load_config
from rulewarden.engine.fixtures import qualify
from rulewarden.engine.loader import load_rules
from rulewarden.engine.lock import build_lock, write_lock

BASIC_RULES = """
version: 1
rules:
  - id: T-001
    title: No print in library code
    source: CLAUDE.md:L3
    severity: required
    decidability: deterministic
    applies_to: ["src/**/*.py"]
    check: {engine: ast, rule: call, names: [print]}
    message: Use logging instead of print().
    fixtures: {fail: ["print('x')"], pass: ["log.info('x')"]}
  - id: T-002
    title: Filler phrase
    severity: advisory
    decidability: deterministic
    applies_to: ["**/*.md", "**/*.py"]
    check: {engine: regex, pattern: '(?i)worth noting', within: comments}
    message: Delete the filler phrase.
    fixtures: {fail: ["# worth noting"], pass: ["# fine"]}
  - id: T-003
    title: Tests are read-only
    severity: critical
    decidability: deterministic
    check: {engine: glob, paths: ["tests/**"], change: [modified, deleted]}
    message: Revert the change to the test.
    fixtures: {fail: ["tests/test_a.py"], pass: ["src/a.py"]}
  - id: T-004
    title: Protected path changed
    severity: critical
    decidability: deterministic
    check: {engine: glob, paths_from: protected, exempt_if_locked: true}
    message: Revert; a human must apply it and lock.
    fixtures: {fail: [".claude/settings.json"], pass: ["src/a.py"]}
  - id: T-005
    title: No force push
    severity: critical
    decidability: deterministic
    scope: command
    check: {engine: regex, on: command, pattern: 'git\\s+push\\s.*--force'}
    message: Do not force push.
    fixtures: {fail: ["git push --force"], pass: ["git push"]}
  - id: T-006
    title: Write clean code
    severity: advisory
    decidability: undecidable
    message: Humans review this.
"""


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    return proc.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "Test")
    git(root, "config", "commit.gpgsign", "false")
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "rules").mkdir()
    (root / ".rulewarden").mkdir()
    (root / "src" / "pkg" / "mod.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    (root / "tests" / "test_mod.py").write_text(
        "def test_f():\n    assert True\n", encoding="utf-8"
    )
    (root / "rules" / "basic.yaml").write_text(BASIC_RULES, encoding="utf-8")
    (root / ".rulewarden" / "approvers").write_text("@human\n", encoding="utf-8")
    (root / ".gitignore").write_text(
        ".rulewarden/audit.jsonl\n.rulewarden/session.json\n.rulewarden/tmp/\n"
    )
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def do_lock(root: Path) -> Config:
    cfg = load_config(root)
    rs = load_rules(cfg)
    rep = qualify(cfg, rs)
    assert rep.passed, [o for o in rep.outcomes if not o.ok]
    write_lock(cfg, build_lock(cfg, rs, rep.summary()))
    return cfg


@pytest.fixture
def locked_repo(repo: Path) -> Path:
    do_lock(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "lock")
    return repo


@pytest.fixture
def lock_fn() -> Callable[[Path], Config]:
    return do_lock
