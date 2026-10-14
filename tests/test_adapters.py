"""Harness contract tests: stdin JSON in, stdout/exit code out, as documented in research/harness-apis.md."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import git

from rulewarden.adapters import ci, claude_code, git_hook, other_harnesses
from rulewarden.config import load_config
from rulewarden.engine import audit


def cc(root: Path, payload: dict[str, object]) -> claude_code.Reply:
    return claude_code.main(load_config(root), json.dumps(payload))


def test_session_start_records_baseline(locked_repo: Path) -> None:
    (locked_repo / "src/pkg/old.py").write_text("print('before session')\n")
    r = cc(
        locked_repo, {"hook_event_name": "SessionStart", "session_id": "s1", "source": "startup"}
    )
    assert r == claude_code.Reply()
    session = json.loads((locked_repo / ".rulewarden/session.json").read_text())
    assert session["session_id"] == "s1" and "src/pkg/old.py" in session["untracked"]
    stop = cc(
        locked_repo, {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": False}
    )
    assert stop.stdout == ""


def test_pretooluse_denies_violating_write_before_actuation(locked_repo: Path) -> None:
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": "s",
        "tool_name": "Write",
        "tool_input": {"file_path": str(locked_repo / "src/pkg/new.py"), "content": "print('x')\n"},
    }
    r = cc(locked_repo, payload)
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny" and "T-001" in out["permissionDecisionReason"]
    assert "nothing was written" in out["permissionDecisionReason"]
    assert not (locked_repo / "src/pkg/new.py").exists()
    ok = dict(
        payload, tool_input={"file_path": str(locked_repo / "src/pkg/new.py"), "content": "x = 1\n"}
    )
    assert cc(locked_repo, ok).stdout == ""


def test_pretooluse_edit_and_multiedit(locked_repo: Path) -> None:
    target = str(locked_repo / "src/pkg/mod.py")
    edit = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": target, "old_string": "return x", "new_string": "print(x)"},
    }
    assert "deny" in cc(locked_repo, edit).stdout
    missing = dict(
        edit, tool_input={"file_path": target, "old_string": "nope", "new_string": "print(x)"}
    )
    assert cc(locked_repo, missing).stdout == ""
    multi = {
        "hook_event_name": "PreToolUse",
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": target,
            "edits": [
                {"old_string": "return x", "new_string": "print(x)", "replace_all": True},
                {"old_string": "absent", "new_string": "y"},
            ],
        },
    }
    assert "deny" in cc(locked_repo, multi).stdout
    nb = {
        "hook_event_name": "PreToolUse",
        "tool_name": "NotebookEdit",
        "tool_input": {
            "notebook_path": str(locked_repo / "src/pkg/nb.py"),
            "new_source": "print(1)",
        },
    }
    assert "deny" in cc(locked_repo, nb).stdout


def test_pretooluse_protects_monitor(locked_repo: Path) -> None:
    for rel in ("rules/basic.yaml", "rules.lock", ".claude/settings.json"):
        r = cc(
            locked_repo,
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": str(locked_repo / rel), "content": "{}\n"},
            },
        )
        assert "T-004" in r.stdout, rel


def test_pretooluse_bash(locked_repo: Path) -> None:
    deny = cc(
        locked_repo,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git push --force"},
        },
    )
    assert json.loads(deny.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert (
        cc(
            locked_repo,
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}},
        ).stdout
        == ""
    )
    assert (
        cc(
            locked_repo, {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {}}
        ).stdout
        == ""
    )


def test_posttooluse_and_stop_feedback(locked_repo: Path) -> None:
    (locked_repo / "src/pkg/mod.py").write_text("def f(x):\n    print(x)\n")
    post = json.loads(
        cc(
            locked_repo, {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {}}
        ).stdout
    )
    assert post["decision"] == "block" and "T-001" in post["reason"]
    stop = json.loads(
        cc(locked_repo, {"hook_event_name": "Stop", "stop_hook_active": False}).stdout
    )
    assert stop["decision"] == "block" and "cannot finish" in stop["reason"]
    (locked_repo / "src/pkg/mod.py").write_text("def f(x):\n    # worth noting\n    return x\n")
    adv = cc(locked_repo, {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {}})
    assert "additionalContext" in adv.stdout
    again = cc(
        locked_repo, {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {}}
    )
    assert again.stdout == ""
    assert cc(locked_repo, {"hook_event_name": "Stop"}).stdout == ""
    assert cc(locked_repo, {"hook_event_name": "Notification"}).stdout == ""


def _stop(root: Path, active: bool) -> claude_code.Reply:
    return cc(root, {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": active})


def test_stop_hook_active_never_blocks_and_records(locked_repo: Path) -> None:
    (locked_repo / "src/pkg/mod.py").write_text("def f(x):\n    print(x)\n")
    r = _stop(locked_repo, True)
    out = json.loads(r.stdout)
    assert r.exit_code == 0 and "decision" not in out and "T-001" in out["systemMessage"]
    entry = list(audit.read(locked_repo))[-1]
    assert entry["outcome"] == "stop_unresolved"
    assert any("T-001" in u for u in entry["unresolved"])  # type: ignore[union-attr]
    needs = (locked_repo / "NEEDS_HUMAN.md").read_text()
    assert needs.count("T-001") == 1
    _stop(locked_repo, True)
    assert (locked_repo / "NEEDS_HUMAN.md").read_text() == needs


def test_stop_protected_path_finding_is_reported_not_blocking(locked_repo: Path) -> None:
    settings = locked_repo / ".claude/settings.json"
    settings.parent.mkdir()
    settings.write_text("{}\n")
    out = json.loads(_stop(locked_repo, False).stdout)
    assert "decision" not in out and "T-004" in out["systemMessage"]
    assert list(audit.read(locked_repo))[-1]["outcome"] == "stop_reported"


def test_stop_pre_existing_violation_does_not_block(locked_repo: Path) -> None:
    (locked_repo / "src/pkg/mod.py").write_text("def f(x):\n    print(x)\n")
    cc(locked_repo, {"hook_event_name": "SessionStart", "session_id": "s1"})
    (locked_repo / "src/pkg/mod.py").write_text(
        "def f(x):\n    print(x)\n\n\ndef g():\n    return 1\n"
    )
    r = _stop(locked_repo, False)
    assert "block" not in r.stdout


def test_stop_blocks_on_new_fixable_required_violation(locked_repo: Path) -> None:
    cc(locked_repo, {"hook_event_name": "SessionStart", "session_id": "s1"})
    (locked_repo / "src/pkg/new.py").write_text("print('agent')\n")
    out = json.loads(_stop(locked_repo, False).stdout)
    assert out["decision"] == "block" and "T-001" in out["reason"]
    assert list(audit.read(locked_repo))[-1]["outcome"] == "stop_blocked"


def test_bad_input_fails_closed(locked_repo: Path) -> None:
    assert claude_code.main(load_config(locked_repo), "not json").exit_code == 2
    assert claude_code.main(load_config(locked_repo), "[]").exit_code == 2
    r = cc(
        locked_repo, {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": "oops"}
    )
    assert r.exit_code == 0


def test_hook_cli_end_to_end(locked_repo: Path) -> None:
    exe = (
        [sys.executable, "-m", "rulewarden.cli"]
        if False
        else [str(Path(sys.executable).parent / "rulewarden")]
    )
    payload = json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git push --force"},
        }
    )
    p = subprocess.run(
        [*exe, "hook", "claude-code", "--root", str(locked_repo)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert p.returncode == 0 and "deny" in p.stdout
    p = subprocess.run(
        [*exe, "hook", "claude-code", "--root", str(locked_repo)],
        input="garbage",
        capture_output=True,
        text=True,
        check=False,
    )
    assert p.returncode == 2 and "failing closed" in p.stderr
    p = subprocess.run(
        [*exe, "hook", "gemini", "--root", str(locked_repo)],
        input="garbage",
        capture_output=True,
        text=True,
        check=False,
    )
    assert p.returncode == 2


def test_settings_merge_keeps_user_hooks() -> None:
    existing = {
        "model": "x",
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "mine"}]},
                {"hooks": [{"type": "command", "command": "old/rulewarden"}]},
            ]
        },
    }
    merged = claude_code.merge_settings(existing, "/opt/rw")
    pre = merged["hooks"]["PreToolUse"]
    assert merged["model"] == "x" and pre[0]["hooks"][0]["command"] == "mine" and len(pre) == 2
    assert pre[1]["hooks"][0]["command"] == "/opt/rw"


def test_git_hooks(locked_repo: Path) -> None:
    cfg = load_config(locked_repo)
    (locked_repo / "src/pkg/mod.py").write_text("print(1)\n")
    git(locked_repo, "add", "-A")
    res, text = git_hook.run(cfg, "pre-commit", (), "")
    assert res.exit_code == 1 and "T-001" in text
    msg = locked_repo / "MSG"
    msg.write_text("feat: worth noting\n# comment line ignored\n")
    res, _ = git_hook.run(cfg, "commit-msg", (str(msg),), "")
    assert [f.rule_id for f in res.findings] == []
    assert git_hook.run(cfg, "commit-msg", (), "")[0].exit_code == 3
    assert git_hook.run(cfg, "bogus", (), "")[0].exit_code == 3
    git(locked_repo, "commit", "-q", "-m", "x", "--no-verify")
    head = git(locked_repo, "rev-parse", "HEAD").strip()
    base = git(locked_repo, "rev-parse", "HEAD~1").strip()
    res, _ = git_hook.run(cfg, "pre-push", (), f"refs/heads/main {head} refs/heads/main {base}\n")
    assert res.exit_code == 1
    res, _ = git_hook.run(
        cfg, "pre-push", (), f"refs/heads/main {head} refs/heads/new {git_hook.ZERO_SHA}\n"
    )
    assert res.exit_code == 1
    res, _ = git_hook.run(
        cfg, "pre-push", (), f"refs/heads/x {git_hook.ZERO_SHA} refs/heads/x {base}\nbad line\n"
    )
    assert res.exit_code == 0
    res, _ = git_hook.run(
        cfg, "pre-push", (), f"refs/heads/main {head} refs/heads/main {'f' * 40}\n"
    )
    assert res.exit_code == 3


def test_git_hook_install_and_script(locked_repo: Path) -> None:
    hooks = locked_repo / ".git/hooks"
    (hooks / "pre-commit").write_text("#!/bin/sh\necho user hook\n")
    written = git_hook.install(locked_repo, "/opt/rw bin/rulewarden")
    assert len(written) == 3 and (hooks / "pre-commit.pre-rulewarden").exists()
    assert "'/opt/rw bin/rulewarden' hook git pre-commit" in (hooks / "pre-commit").read_text()
    assert git_hook.default_binary(locked_repo)


def test_real_git_commit_is_blocked(locked_repo: Path) -> None:
    exe = str(Path(sys.executable).parent / "rulewarden")
    git_hook.install(locked_repo, exe)
    (locked_repo / "src/pkg/mod.py").write_text("print(1)\n")
    git(locked_repo, "add", "-A")
    p = subprocess.run(
        ["git", "commit", "-m", "feat: x"],
        cwd=locked_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert p.returncode != 0 and "T-001" in p.stderr
    (locked_repo / "src/pkg/mod.py").write_text("x = 1\n")
    git(locked_repo, "add", "-A")
    p = subprocess.run(
        ["git", "commit", "-m", "feat: x"],
        cwd=locked_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert p.returncode == 0, p.stderr


def test_ci_adapter(locked_repo: Path) -> None:
    cfg = load_config(locked_repo)
    (locked_repo / "src/pkg/mod.py").write_text("# worth noting\nprint(1)\n")
    git(locked_repo, "add", "-A")
    git(locked_repo, "commit", "-q", "-m", "x", "--no-verify")
    res = ci.check_range(cfg, "HEAD~1")
    lines = ci.gh_annotations(res)
    assert lines[0].startswith("::error file=src/pkg/mod.py,line=2") and lines[1].startswith(
        "::warning"
    )
    assert ci.check_range(cfg, "nope-rev").exit_code == 3
    cmd = ci.gh_annotations(
        type(res)(
            findings=[
                res.findings[0].__class__(
                    **{**res.findings[0].__dict__, "path": ":command", "line": None}
                )
            ]
        )
    )
    assert cmd[0].startswith("::error title=")


def test_codex_adapter(locked_repo: Path) -> None:
    cfg = load_config(locked_repo)
    patch = "*** Begin Patch\n*** Add File: src/pkg/n.py\n+print(1)\n*** End Patch\n"
    r = other_harnesses.codex(
        cfg,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"command": patch},
        },
    )
    assert "deny" in r.stdout
    clean = patch.replace("print(1)", "x = 1")
    assert (
        other_harnesses.codex(
            cfg,
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {"command": clean},
            },
        ).stdout
        == ""
    )
    r = other_harnesses.codex(
        cfg,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git push --force"},
        },
    )
    assert "deny" in r.stdout


def test_gemini_adapter(locked_repo: Path) -> None:
    cfg = load_config(locked_repo)
    r = other_harnesses.gemini(
        cfg,
        {
            "hook_event_name": "BeforeTool",
            "tool_name": "run_shell_command",
            "tool_input": {"command": "git push --force"},
        },
    )
    assert json.loads(r.stdout)["decision"] == "deny"
    r = other_harnesses.gemini(
        cfg,
        {
            "hook_event_name": "BeforeTool",
            "tool_name": "replace",
            "tool_input": {
                "file_path": str(locked_repo / "src/pkg/mod.py"),
                "old_string": "return x",
                "new_string": "print(x)",
                "allow_multiple": True,
            },
        },
    )
    assert json.loads(r.stdout)["decision"] == "deny"
    assert other_harnesses.gemini(cfg, {"hook_event_name": "AfterTool"}).stdout == ""
    assert (
        other_harnesses.gemini(
            cfg, {"hook_event_name": "BeforeTool", "tool_name": "read_file"}
        ).stdout
        == ""
    )
    assert (
        other_harnesses.gemini(
            cfg,
            {
                "hook_event_name": "BeforeTool",
                "tool_name": "run_shell_command",
                "tool_input": {"command": "ls"},
            },
        ).stdout
        == ""
    )


def test_opencode_adapter(locked_repo: Path) -> None:
    cfg = load_config(locked_repo)
    r = other_harnesses.opencode(
        cfg,
        {
            "tool": "write",
            "args": {"filePath": str(locked_repo / "src/pkg/z.py"), "content": "print(1)\n"},
        },
    )
    assert json.loads(r.stdout)["block"] is True
    assert (
        json.loads(other_harnesses.opencode(cfg, {"tool": "read", "args": {}}).stdout)["block"]
        is False
    )
    assert (
        json.loads(
            other_harnesses.opencode(cfg, {"tool": "bash", "args": {"command": "ls"}}).stdout
        )["block"]
        is False
    )
    assert "spawnSync" in other_harnesses.OPENCODE_PLUGIN


@pytest.mark.parametrize("harness", ["codex", "opencode"])
def test_other_harness_cli(locked_repo: Path, harness: str) -> None:
    exe = str(Path(sys.executable).parent / "rulewarden")
    payload = {
        "codex": {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git push --force"},
        },
        "opencode": {"tool": "bash", "args": {"command": "git push --force"}},
    }[harness]
    p = subprocess.run(
        [exe, "hook", harness, "--root", str(locked_repo)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert p.returncode == 0 and ("deny" in p.stdout or '"block": true' in p.stdout)


def test_git_and_ci_cli(locked_repo: Path) -> None:
    exe = str(Path(sys.executable).parent / "rulewarden")
    (locked_repo / "src/pkg/mod.py").write_text("print(1)\n")
    git(locked_repo, "add", "-A")
    p = subprocess.run(
        [exe, "hook", "pre-commit", "--root", str(locked_repo)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert p.returncode == 1 and "T-001" in p.stderr
    git(locked_repo, "commit", "-q", "-m", "x", "--no-verify")
    p = subprocess.run(
        [exe, "hook", "ci", "HEAD~1", "--root", str(locked_repo)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert p.returncode == 1 and p.stdout.startswith("::error")


def test_pretooluse_edit_of_file_created_this_session_is_not_a_modification(
    locked_repo: Path,
) -> None:
    cc(locked_repo, {"hook_event_name": "SessionStart", "session_id": "s1"})
    new_test = locked_repo / "tests/test_new.py"
    new_test.write_text("def test_a():\n    assert 1\n")
    r = cc(
        locked_repo,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(new_test),
                "old_string": "assert 1",
                "new_string": "assert 2",
            },
        },
    )
    assert r.stdout == ""
    existing = locked_repo / "tests/test_mod.py"
    r = cc(
        locked_repo,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(existing),
                "old_string": "assert True",
                "new_string": "assert False",
            },
        },
    )
    assert "T-003" in r.stdout
