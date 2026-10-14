import os
import subprocess
import tarfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup.sh"


def run(*args, now=None):
    env = dict(os.environ)
    if now:
        env["BACKUP_NOW"] = now
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env)


def src(tmp_path):
    s = tmp_path / "src"
    (s / "sub").mkdir(parents=True)
    (s / "a.txt").write_text("A")
    (s / "sub" / "b.txt").write_text("B")
    return s


def names(archive):
    with tarfile.open(archive) as t:
        return {n.lstrip("./") for n in t.getnames() if n.lstrip("./")}


def test_creates_archive_with_relative_paths(tmp_path):
    dest = tmp_path / "out" / "nested"
    r = run(str(src(tmp_path)), str(dest), now="20260101-120000")
    assert r.returncode == 0, r.stderr
    archive = dest / "backup-20260101-120000.tar.gz"
    assert r.stdout.strip() == str(archive) and archive.exists()
    assert {"a.txt", "sub/b.txt"} <= names(archive)
    assert not any(n.startswith(str(tmp_path).lstrip("/")) for n in names(archive))


def test_rotation_keeps_newest_and_other_files(tmp_path):
    s, dest = src(tmp_path), tmp_path / "dest"
    dest.mkdir()
    (dest / "notes.txt").write_text("keep me")
    (dest / "backup-old.tar.gz.part").write_text("keep me too")
    for stamp in ["20260101-000001", "20260101-000002", "20260101-000003", "20260101-000004"]:
        assert run(str(s), str(dest), "2", now=stamp).returncode == 0
    left = sorted(p.name for p in dest.iterdir())
    assert left == ["backup-20260101-000003.tar.gz", "backup-20260101-000004.tar.gz", "backup-old.tar.gz.part", "notes.txt"]


def test_default_keep_is_five(tmp_path):
    s, dest = src(tmp_path), tmp_path / "dest"
    for i in range(7):
        run(str(s), str(dest), now=f"20260101-00000{i}")
    assert len(list(dest.glob("backup-*.tar.gz"))) == 5


def test_errors(tmp_path):
    assert run(str(tmp_path)).returncode == 2
    assert run(str(tmp_path / "missing"), str(tmp_path / "d")).returncode == 1
    s = src(tmp_path)
    for bad in ["0", "-1", "x"]:
        assert run(str(s), str(tmp_path / "d"), bad).returncode == 2


def test_spaces_in_paths(tmp_path):
    s = tmp_path / "my src"
    s.mkdir()
    (s / "f.txt").write_text("x")
    dest = tmp_path / "my dest"
    r = run(str(s), str(dest), now="20260202-020202")
    assert r.returncode == 0, r.stderr
    assert (dest / "backup-20260202-020202.tar.gz").exists()
