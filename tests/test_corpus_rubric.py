"""The corpus rubric labels the examples given in corpus/README.md as documented."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"corpus_{name}", ROOT / "corpus" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


label = _load("label")
extract = _load("extract")


@pytest.mark.parametrize(
    ("text", "tier"),
    [
        ("Never commit .env files", "deterministic"),
        ("Use pnpm instead of npm", "deterministic"),
        ("Keep functions under 50 lines", "deterministic"),
        ("Keep functions short", "heuristic"),
        ("Avoid redundant comments", "heuristic"),
        ("Write clean code", "undecidable"),
        ("Think before acting", "undecidable"),
    ],
)
def test_decidability_examples(text: str, tier: str) -> None:
    assert label.decidability(text) == tier


@pytest.mark.parametrize(
    ("text", "cat"),
    [
        ("Never commit API keys", "security"),
        ("Always write tests for new code", "testing"),
        ("Do not modify files outside src/", "scope"),
        ("Use Conventional Commits for commit messages", "process"),
        ("Use pnpm instead of npm", "tooling"),
        ("Do not use emojis in comments", "voice"),
        ("Use camelCase for variable names", "style"),
        ("Be nice", "other"),
    ],
)
def test_category_examples(text: str, cat: str) -> None:
    assert label.category(text) == cat


def test_compilable_flag_uses_compile_templates() -> None:
    assert label.label("Use pnpm instead of npm")["compilable"] == "1"
    assert label.label("Write clean code")["compilable"] == "0"


def test_scrub_masks_secrets_emails_and_handles() -> None:
    pats = extract.secret_patterns()
    assert extract.scrub("token ghp_" + "0" * 36, pats) == ("", True)
    text, red = extract.scrub("Mail dev@example.com or ping @octocat", pats)
    assert not red and "<email>" in text and "@<handle>" in text and "octocat" not in text


@pytest.mark.parametrize(
    ("text", "tier"),
    [
        ("Tests use .mjs extension", "undecidable"),
        ("Run `xcodegen` to pick up the new file", "undecidable"),
        ("Never run `rm -rf` on the home directory", "deterministic"),
        ("CRITICAL: Use `julia --project=<env>` when running Julia code", "deterministic"),
        ("No `console.log` in committed code", "deterministic"),
    ],
)
def test_descriptions_and_obligations(text: str, tier: str) -> None:
    assert label.decidability(text) == tier
