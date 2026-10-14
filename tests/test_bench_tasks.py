"""Every benchmark task is well-formed, qualified, solvable, and solvable without violations."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bench.harness import tasks, workspace  # noqa: E402
from rulewarden.config import load_config  # noqa: E402
from rulewarden.engine.fixtures import qualify  # noqa: E402
from rulewarden.engine.loader import load_rules  # noqa: E402

IDS = tasks.all_ids()


def test_enough_tasks() -> None:
    assert len(IDS) >= 1


def test_library_qualifies(tmp_path: Path) -> None:
    lib = tmp_path / ".rulewarden" / "rules"
    lib.mkdir(parents=True)
    shutil.copy(tasks.LIBRARY, lib / "library.yaml")
    (tmp_path / ".rulewarden" / "config.yaml").write_text(
        "version: 1\nrules: [.rulewarden/rules]\n"
    )
    cfg = load_config(tmp_path)
    assert qualify(cfg, load_rules(cfg)).passed


@pytest.mark.parametrize("task_id", IDS)
def test_task_rules_qualify(task_id: str, tmp_path: Path) -> None:
    task = tasks.load(task_id)
    workspace.install_rules(task, tmp_path)
    cfg = load_config(tmp_path)
    rep = qualify(cfg, load_rules(cfg))
    assert rep.passed, rep.summary()
    severities = {r["severity"] for r in task.rules}
    tiers = {r["decidability"] for r in task.rules}
    assert {"critical", "required"} & severities and "advisory" in severities
    assert "deterministic" in tiers


def _solve(task: tasks.Task, dest: Path) -> str:
    base = workspace.prepare(task, dest, "B")
    shutil.copytree(task.dir / "reference", dest, dirs_exist_ok=True)
    return base


@pytest.mark.parametrize("task_id", IDS)
def test_reference_passes_hidden_tests_cleanly(task_id: str, tmp_path: Path) -> None:
    task = tasks.load(task_id)
    dest = tmp_path / "ws"
    base = _solve(task, dest)
    code, out = workspace.run_hidden_tests(task, dest)
    assert code == 0, out
    result = workspace.score(task.rules_yaml(), workspace.final_diff(dest, base), tmp_path)
    assert result["viol_any"] == 0 and not result["errors"], result


@pytest.mark.parametrize("task_id", IDS)
def test_starting_repo_fails_hidden_tests(task_id: str, tmp_path: Path) -> None:
    task = tasks.load(task_id)
    dest = tmp_path / "ws"
    workspace.prepare(task, dest, "A")
    code, _ = workspace.run_hidden_tests(task, dest)
    assert code != 0


@pytest.mark.parametrize("task_id", IDS[:1])
def test_hooked_workspace_is_locked_and_clean(task_id: str, tmp_path: Path) -> None:
    task = tasks.load(task_id)
    dest = tmp_path / "ws"
    workspace.prepare(task, dest, "C")
    assert (dest / ".claude" / "settings.json").exists() and (dest / "rules.lock").exists()
    proc = subprocess.run(
        [str(workspace.RULEWARDEN), "lock", "--check", "--root", str(dest)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "## Rules" in (dest / "CLAUDE.md").read_text()
