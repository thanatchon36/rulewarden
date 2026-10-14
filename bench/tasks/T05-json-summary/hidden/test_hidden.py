import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "summarize.sh"


def run(*args):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True)


def orders(tmp_path, data):
    f = tmp_path / "orders.json"
    f.write_text(json.dumps(data))
    return str(f)


def test_summary(tmp_path):
    data = [
        {"id": 1, "customer": "bob", "total": 10.5, "status": "paid"},
        {"id": 2, "customer": "ann", "total": 3, "status": "refunded"},
        {"id": 3, "customer": "ann", "total": 7.25, "status": "paid"},
        {"id": 4, "customer": "cy", "total": 99, "status": "pending"},
        {"id": 5, "customer": "ann", "total": 4, "status": "paid"},
    ]
    r = run(orders(tmp_path, data))
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == ["orders: 5", "paid: 3", "revenue: 21.75", "top: ann"]


def test_tie_goes_to_alphabetical(tmp_path):
    data = [
        {"id": 1, "customer": "zed", "total": 5, "status": "paid"},
        {"id": 2, "customer": "amy", "total": 5, "status": "paid"},
    ]
    assert run(orders(tmp_path, data)).stdout.splitlines()[3] == "top: amy"


def test_no_paid_orders(tmp_path):
    r = run(orders(tmp_path, [{"id": 1, "customer": "a", "total": 1, "status": "pending"}]))
    assert r.stdout.splitlines() == ["orders: 1", "paid: 0", "revenue: 0.00", "top: -"]


def test_empty_array(tmp_path):
    assert run(orders(tmp_path, [])).stdout.splitlines() == ["orders: 0", "paid: 0", "revenue: 0.00", "top: -"]


def test_usage():
    r = run()
    assert r.returncode == 2 and "usage: summarize.sh FILE" in r.stderr


def test_missing_and_invalid(tmp_path):
    assert run(str(tmp_path / "none.json")).returncode == 1
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    r = run(str(bad))
    assert r.returncode == 1 and r.stdout == ""


def test_spaces_in_path(tmp_path):
    d = tmp_path / "with space"
    d.mkdir()
    f = d / "o.json"
    f.write_text(json.dumps([{"id": 1, "customer": "a", "total": 2, "status": "paid"}]))
    assert run(str(f)).stdout.splitlines()[2] == "revenue: 2.00"
