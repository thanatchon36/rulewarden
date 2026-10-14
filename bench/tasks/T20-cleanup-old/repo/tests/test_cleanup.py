import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cleanup.sh"


def test_refuses_root():
    assert subprocess.run(["bash", str(SCRIPT), "/", "1"], capture_output=True).returncode == 1
