import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-env.sh"


def run(args, cwd=None, extra=None):
    env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp")}
    env.update(extra or {})
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, cwd=cwd, env=env)


def test_mixed(tmp_path):
    f = tmp_path / "req"
    f.write_text("# needed\nAPI_URL\n\n  EMPTY_ONE  \ncmd:bash\ncmd:definitely-not-a-cmd-xyz\nMISSING_VAR\n")
    r = run([str(f)], extra={"API_URL": "http://x", "EMPTY_ONE": ""})
    assert r.returncode == 1
    assert r.stdout.splitlines() == [
        "ok API_URL",
        "missing EMPTY_ONE",
        "ok cmd bash",
        "missing cmd definitely-not-a-cmd-xyz",
        "missing MISSING_VAR",
    ]


def test_all_present_default_file(tmp_path):
    (tmp_path / "env.required").write_text("HOME\ncmd:ls\n")
    r = run([], cwd=tmp_path)
    assert r.returncode == 0 and r.stdout.splitlines() == ["ok HOME", "ok cmd ls"]


def test_invalid_lines_do_not_execute(tmp_path):
    marker = tmp_path / "pwned"
    f = tmp_path / "req"
    f.write_text(f"$(touch {marker})\n1BAD\nHOME\n")
    r = run([str(f)])
    assert not marker.exists()
    assert r.returncode == 1
    assert r.stdout.splitlines() == [f"invalid $(touch {marker})", "invalid 1BAD", "ok HOME"]


def test_missing_file(tmp_path):
    r = run([str(tmp_path / "nope")])
    assert r.returncode == 2 and r.stderr
