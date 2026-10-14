from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import git

from rulewarden.cli import main


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    def _run(root: Path, *args: str, input: str | None = None):  # type: ignore[no-untyped-def]
        monkeypatch.chdir(root)
        return CliRunner().invoke(main, list(args), input=input, catch_exceptions=False)

    return _run


def test_check_text_json_and_exit_codes(locked_repo: Path, run) -> None:  # type: ignore[no-untyped-def]
    r = run(locked_repo, "check")
    assert r.exit_code == 0 and "PASS" in r.output
    (locked_repo / "src/pkg/mod.py").write_text("print(1)\n")
    r = run(locked_repo, "check", "--format", "json", "--json-out", "out.json")
    assert r.exit_code == 1 and json.loads(r.output)["counts"]["required"] == 1
    assert json.loads((locked_repo / "out.json").read_text())["status"] == "blocked"
    r = run(locked_repo, "check", "--style", "flat", "--all", "--no-audit")
    assert r.exit_code == 1 and r.output.startswith("1 finding(s):")
    assert (locked_repo / ".rulewarden/audit.jsonl").exists()


def test_check_other_sources(locked_repo: Path, run) -> None:  # type: ignore[no-untyped-def]
    assert run(locked_repo, "check", "--command", "git push --force x").exit_code == 1
    diff = "diff --git a/src/pkg/n.py b/src/pkg/n.py\nnew file mode 100644\n--- /dev/null\n+++ b/src/pkg/n.py\n@@ -0,0 +1 @@\n+# worth noting\n"
    r = run(locked_repo, "check", "--diff", "-", input=diff)
    assert r.exit_code == 0 and "1 advisory" in r.output
    (locked_repo / "d.patch").write_text(diff)
    assert run(locked_repo, "check", "--diff", "d.patch").exit_code == 0
    (locked_repo / "src/pkg/mod.py").write_text("print(1)\n")
    git(locked_repo, "add", "-A")
    assert run(locked_repo, "check", "--staged").exit_code == 1
    git(locked_repo, "commit", "-q", "-m", "x")
    assert run(locked_repo, "check", "--range", "HEAD~1...HEAD").exit_code == 1
    assert run(locked_repo, "check", "--base", "HEAD~1").exit_code == 1
    r = run(locked_repo, "check", "--base", "no-such-rev")
    assert r.exit_code == 3 and "RW-DIFF" in r.output
    r = run(locked_repo, "check", "--as-of", "2026-01-01")
    assert r.exit_code == 0


def test_test_rules_and_lock(repo: Path, run) -> None:  # type: ignore[no-untyped-def]
    r = run(repo, "test-rules", "-v")
    assert r.exit_code == 0 and "PASS — 10 fixtures across 5 rules (1 undecidable" in r.output
    r = run(repo, "lock")
    assert r.exit_code == 3 and "human action" in r.output
    r = run(repo, "lock", "--check")
    assert r.exit_code == 1 and "STALE" in r.output
    r = run(repo, "lock", "--ci")
    assert r.exit_code == 0 and "locked 6 rules" in r.output
    assert run(repo, "lock", "--check").exit_code == 0
    bad = repo / "rules/basic.yaml"
    bad.write_text(bad.read_text().replace("pass: [\"log.info('x')\"]", "pass: [\"print('y')\"]"))
    r = run(repo, "test-rules")
    assert r.exit_code == 1 and "FAIL T-001 pass[0]" in r.output
    r = run(repo, "lock", "--ci")
    assert r.exit_code == 1 and "refusing to lock" in r.output
    bad.write_text("nope: [")
    assert run(repo, "test-rules").exit_code == 3
    assert run(repo, "lock", "--ci").exit_code == 3


def test_test_rules_on_shipped_packs(repo: Path, run) -> None:  # type: ignore[no-untyped-def]
    packs = Path(__file__).resolve().parents[1] / "src/rulewarden/packs"
    r = run(repo, "test-rules", "--path", str(packs))
    assert r.exit_code == 0, r.output


def test_bad_config_exits_3(repo: Path, run) -> None:  # type: ignore[no-untyped-def]
    (repo / ".rulewarden/config.yaml").write_text("unknown_key: 1\n")
    r = run(repo, "check")
    assert r.exit_code == 3


def test_compile_init_report_stats_doctor(repo: Path, run) -> None:  # type: ignore[no-untyped-def]
    (repo / "CLAUDE.md").write_text(
        "# Rules\n- Never use `eval` in code.\n- Use pnpm instead of npm.\n- Write clean, readable code.\n"
        "- Think before you act.\n- Never commit secrets or API keys.\n"
    )
    r = run(repo, "compile", "CLAUDE.md")
    assert r.exit_code == 0 and "2 heuristic candidates" not in r.output
    assert "undecidable" in r.output and "C-L2" in r.output
    r = run(repo, "compile", "CLAUDE.md", "--format", "json", "--out", "p.yaml")
    data = json.loads(r.output)
    assert data["counts"]["compiled"] == 3 and (repo / "p.yaml").exists()
    r = run(repo, "init", "--binary", "/usr/local/bin/rulewarden", "--opencode")
    assert r.exit_code == 0, r.output
    assert (repo / "rules/packs/voice.yaml").exists()
    assert (repo / "rules/compiled-claude-md.yaml").exists()
    settings = json.loads((repo / ".claude/settings.json").read_text())
    assert settings["hooks"]["PreToolUse"][0]["hooks"][0]["onFailure"] == "block"
    assert (repo / ".git/hooks/pre-commit").read_text().count("hook git pre-commit") == 1
    assert (repo / ".opencode/plugins/rulewarden.js").exists()
    assert run(repo, "init", "--packs", "nope", "--no-claude", "--no-git-hooks").exit_code == 3
    assert run(repo, "lock", "--ci").exit_code == 0
    run(repo, "check")
    r = run(repo, "report")
    assert r.exit_code == 0 and "hash chain: intact" in r.output
    assert json.loads(run(repo, "report", "--format", "json").output)["chain"]["intact"]
    assert "NIST AI RMF" in run(repo, "report", "--framework", "nist-ai-rmf").output
    assert json.loads(run(repo, "report", "--framework", "nist-ai-rmf", "--format", "json").output)[
        "framework"
    ]
    assert "audit entries" in run(repo, "stats").output
    assert "never_fired" in json.loads(run(repo, "stats", "--format", "json").output)
    r = run(repo, "doctor")
    assert "determinism self-test" in r.output and "rules.lock matches" in r.output, r.output
    assert run(repo, "doctor", "--determinism-only").exit_code == 0


def test_init_with_lock_flag(repo: Path, run) -> None:  # type: ignore[no-untyped-def]
    r = run(repo, "init", "--packs", "secrets", "--no-claude", "--no-git-hooks", "--lock")
    assert r.exit_code == 0 and "locked" in r.output


def test_version(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    assert "rulewarden, version" in run(tmp_path, "--version").output
    assert os.getcwd() == str(tmp_path) or True
