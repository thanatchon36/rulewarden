import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "git-stats.sh"


def test_not_a_repo(tmp_path):
    assert subprocess.run(["bash", str(SCRIPT), str(tmp_path)], capture_output=True).returncode == 1
