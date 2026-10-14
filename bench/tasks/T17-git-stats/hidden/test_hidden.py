import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "git-stats.sh"


def git(repo, *args, author=None, date=None):
    env = dict(os.environ)
    env.update({"GIT_COMMITTER_NAME": "c", "GIT_COMMITTER_EMAIL": "c@x"})
    if date:
        env.update({"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
    cmd = ["git", "-C", str(repo), "-c", "commit.gpgsign=false"]
    if author:
        cmd += ["-c", f"user.name={author}", "-c", "user.email=a@x"]
    subprocess.run(cmd + list(args), check=True, capture_output=True, env=env)


def make_repo(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    commits = [("Zoë Ward", "2026-01-01T00:00:00"), ("ann lee", "2026-02-01T00:00:00"),
               ("Zoë Ward", "2026-03-01T00:00:00"), ("Bob", "2026-03-02T00:00:00"),
               ("ann lee", "2026-03-03T00:00:00"), ("Zoë Ward", "2026-03-04T00:00:00")]
    for i, (who, when) in enumerate(commits):
        git(repo, "commit", "-q", "--allow-empty", "-m", f"c{i}", author=who, date=when)
    return repo


def run(*args, cwd=None):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, cwd=cwd)


def test_counts_sorted(tmp_path):
    r = run(str(make_repo(tmp_path)))
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == ["3 Zoë Ward", "2 ann lee", "1 Bob", "total: 6"]


def test_default_repo_is_cwd(tmp_path):
    assert run(cwd=make_repo(tmp_path)).stdout.splitlines()[-1] == "total: 6"


def test_since(tmp_path):
    r = run("--since", "2026-03-01T12:00:00", str(make_repo(tmp_path)))
    assert r.stdout.splitlines() == ["1 Bob", "1 Zoë Ward", "1 ann lee", "total: 3"]


def test_empty_repo(tmp_path):
    repo = tmp_path / "e"
    repo.mkdir()
    git(repo, "init", "-q")
    r = run(str(repo))
    assert r.returncode == 0 and r.stdout == "total: 0\n"


def test_errors(tmp_path):
    assert run(str(tmp_path)).returncode == 1
    assert run("--bogus", str(tmp_path)).returncode == 2
