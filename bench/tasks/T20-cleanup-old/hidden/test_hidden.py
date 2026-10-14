import os
import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cleanup.sh"
DAY = 86400


def run(*args, home=None):
    env = dict(os.environ)
    if home:
        env["HOME"] = str(home)
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env)


def touch(path, age_days):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    t = time.time() - age_days * DAY
    os.utime(path, (t, t))
    return path


def tree(tmp_path):
    d = tmp_path / "work"
    touch(d / "old.tmp", 10)
    touch(d / "new.tmp", 1)
    touch(d / "old.log", 10)
    touch(d / "sub" / "deep.tmp", 30)
    touch(d / "sub dir" / "spaced old.tmp", 30)
    outside = touch(tmp_path / "outside.tmp", 99)
    (d / "link.tmp").symlink_to(outside)
    os.utime(d / "link.tmp", (time.time() - 99 * DAY,) * 2, follow_symlinks=False)
    return d


def test_deletes_matching_old_files(tmp_path):
    d = tree(tmp_path)
    r = run(str(d), "5", "*.tmp")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == sorted([str(d / "old.tmp"), str(d / "sub dir" / "spaced old.tmp"), str(d / "sub" / "deep.tmp")])
    assert not (d / "old.tmp").exists() and (d / "new.tmp").exists() and (d / "old.log").exists()
    assert (d / "link.tmp").is_symlink() and (tmp_path / "outside.tmp").exists()
    assert (d / "sub").is_dir()


def test_default_pattern_and_dry_run(tmp_path):
    d = tree(tmp_path)
    r = run("-n", str(d), "5")
    assert r.returncode == 0
    assert str(d / "old.log") in r.stdout.splitlines() and str(d / "new.tmp") not in r.stdout
    assert (d / "old.log").exists() and (d / "old.tmp").exists()


def test_refusals(tmp_path):
    assert run("", "1").returncode == 1
    assert run("/", "1").returncode == 1
    home = tmp_path / "home"
    home.mkdir()
    assert run(str(home), "1", home=home).returncode == 1
    assert run(str(tmp_path / "missing"), "1").returncode == 1


def test_usage(tmp_path):
    assert run(str(tmp_path)).returncode == 2
    assert run(str(tmp_path), "-3").returncode == 2
    assert run(str(tmp_path), "x").returncode == 2
