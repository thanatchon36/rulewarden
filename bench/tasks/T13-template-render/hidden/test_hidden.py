import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render.sh"


def run(tmp_path, template, values):
    t = tmp_path / "t.tmpl"
    t.write_text(template)
    v = tmp_path / "v.json"
    v.write_text(values if isinstance(values, str) else json.dumps(values))
    return subprocess.run(["bash", str(SCRIPT), str(t), str(v)], capture_output=True, text=True)


def test_basic_and_dotted(tmp_path):
    r = run(tmp_path, "host={{db.host}}:{{db.port}} debug={{debug}}\nname={{name}}\n",
            {"db": {"host": "db.local", "port": 5432}, "debug": True, "name": "app"})
    assert r.returncode == 0, r.stderr
    assert r.stdout == "host=db.local:5432 debug=true\nname=app\n"


def test_special_characters_survive(tmp_path):
    val = "a/b & c\\d $HOME `x` {{name}}\nline2"
    r = run(tmp_path, "v={{v}}", {"v": val, "name": "n"})
    assert r.returncode == 0 and r.stdout == "v=" + val


def test_repeated_placeholder(tmp_path):
    assert run(tmp_path, "{{a}}-{{a}}\n", {"a": "x"}).stdout == "x-x\n"


def test_bad_keys_reported_once_in_order(tmp_path):
    r = run(tmp_path, "{{zeta}} {{a.b}} {{zeta}} {{obj}} {{nul}} {{ok}}", {"obj": {}, "nul": None, "ok": 1})
    assert r.returncode == 1 and r.stdout == ""
    assert r.stderr.splitlines() == [
        "render.sh: bad key zeta",
        "render.sh: bad key a.b",
        "render.sh: bad key obj",
        "render.sh: bad key nul",
    ]


def test_no_placeholders_and_no_trailing_newline(tmp_path):
    assert run(tmp_path, "plain text", {}).stdout == "plain text"


def test_errors(tmp_path):
    assert run(tmp_path, "x", "{bad json").returncode == 1
    r = subprocess.run(["bash", str(SCRIPT), str(tmp_path / "missing"), str(tmp_path / "m.json")], capture_output=True)
    assert r.returncode == 1
    assert subprocess.run(["bash", str(SCRIPT), "one"], capture_output=True).returncode == 2
