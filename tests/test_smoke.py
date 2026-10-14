from click.testing import CliRunner

from rulewarden import __version__
from rulewarden.cli import main


def test_version_flag_reports_package_version() -> None:
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
