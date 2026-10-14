"""What `rulewarden init` tells the user about compiled lines that the vendored packs already cover."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from rulewarden.cli import main


def _init(root: Path, monkeypatch) -> str:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(root)
    r = CliRunner().invoke(main, ["init", "--no-git-hooks"], catch_exceptions=False)
    assert r.exit_code == 0, r.output
    return r.output


def test_init_names_rules_already_covered_by_packs(repo: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    (repo / "CLAUDE.md").write_text("# Rules\n- No print() in src/; use logging.\n")
    out = _init(repo, monkeypatch)
    assert "already enforced by the vendored packs" in out
    assert not list((repo / "rules").glob("compiled-*.yaml"))


def test_init_reports_no_coverage_line_for_novel_rules(repo: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    (repo / "CLAUDE.md").write_text("# Rules\n- Use pnpm instead of npm.\n")
    out = _init(repo, monkeypatch)
    assert "already enforced" not in out
    assert "project-specific rules" in out
