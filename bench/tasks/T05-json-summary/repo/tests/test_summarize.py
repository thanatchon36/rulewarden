import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "summarize.sh"


def test_counts(tmp_path):
    f = tmp_path / "o.json"
    f.write_text(json.dumps([{"id": 1, "customer": "a", "total": 5, "status": "paid"}]))
    out = subprocess.run(["bash", str(SCRIPT), str(f)], capture_output=True, text=True)
    assert out.stdout.splitlines()[0] == "orders: 1"
