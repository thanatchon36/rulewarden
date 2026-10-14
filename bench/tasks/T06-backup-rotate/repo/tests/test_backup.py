import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup.sh"


def test_usage():
    assert subprocess.run(["bash", str(SCRIPT)], capture_output=True).returncode == 2
