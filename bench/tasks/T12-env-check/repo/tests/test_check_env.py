import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-env.sh"


def test_missing_file(tmp_path):
    r = subprocess.run(["bash", str(SCRIPT), str(tmp_path / "none")], capture_output=True)
    assert r.returncode == 2
