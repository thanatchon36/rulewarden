"""Command-line entry point."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

import click

from rulewarden import __version__
from rulewarden.config import Config, load_config
from rulewarden.engine import audit
from rulewarden.engine.report import EXIT_ERROR, Result, render_text, to_json
from rulewarden.errors import RulewardenError


def _root(start: str | None) -> Path:
    from rulewarden.engine.gitsrc import repo_root

    base = Path(start or os.getcwd()).resolve()
    try:
        return repo_root(base)
    except RulewardenError:
        return base


def _config(root_opt: str | None) -> Config:
    root = _root(root_opt)
    try:
        return load_config(root)
    except RulewardenError as exc:
        click.echo(f"ERROR — {exc}", err=True)
        sys.exit(EXIT_ERROR)


def emit(
    result: Result, cfg: Config, fmt: str, style: str | None, show_all: bool, json_out: str | None
) -> None:
    if json_out:
        Path(json_out).write_text(to_json(result), encoding="utf-8")
    if fmt == "json":
        click.echo(to_json(result), nl=False)
    else:
        cap = 10**9 if show_all else cfg.report.advisory_cap
        max_chars = 0 if show_all else cfg.report.max_chars
        click.echo(render_text(result, style or cfg.report.style, cap, max_chars), nl=False)


@click.group()
@click.version_option(__version__, prog_name="rulewarden")
def main() -> None:
    """Deterministic runtime assurance for AI coding agents."""


@main.command()
@click.option(
    "--root", type=click.Path(file_okay=False), help="Repository root (default: git toplevel)."
)
@click.option("--staged", "source", flag_value="staged", help="Check the index against HEAD.")
@click.option(
    "--working-tree",
    "source",
    flag_value="worktree",
    default=True,
    help="Check the working tree against the baseline (default).",
)
@click.option(
    "--diff",
    "diff_file",
    type=click.Path(dir_okay=False, allow_dash=True),
    help="Check a unified diff file ('-' for stdin).",
)
@click.option(
    "--base", help="Baseline revision (default: session baseline, then config, then HEAD)."
)
@click.option("--range", "rev_range", help="Check BASE...HEAD (CI mode), e.g. origin/main...HEAD.")
@click.option("--command", "command", help="Check a shell command against command-scope rules.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.option("--style", type=click.Choice(["managed", "flat"]), default=None)
@click.option(
    "--all", "show_all", is_flag=True, help="Show every finding (no advisory or length cap)."
)
@click.option(
    "--json-out", type=click.Path(dir_okay=False), help="Also write the JSON report here."
)
@click.option(
    "--as-of",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Date for deviation expiry (default: today UTC).",
)
@click.option("--no-audit", is_flag=True, help="Do not append to the audit log.")
@click.option("--harness", default="cli", help="Harness name recorded in the audit log.")
def check(
    root: str | None,
    source: str,
    diff_file: str | None,
    base: str | None,
    rev_range: str | None,
    command: str | None,
    fmt: str,
    style: str | None,
    show_all: bool,
    json_out: str | None,
    as_of: date | None,
    no_audit: bool,
    harness: str,
) -> None:
    """Run the rules on a change; exit 0 pass, 1 blocked, 3 engine error."""
    from rulewarden.engine import gitsrc
    from rulewarden.engine.runner import Request, run_check

    cfg = _config(root)
    t0 = time.monotonic()
    diff = None
    try:
        if command is None or diff_file or rev_range or source == "staged":
            if diff_file:
                text = (
                    sys.stdin.read()
                    if diff_file == "-"
                    else Path(diff_file).read_text(encoding="utf-8")
                )
                diff = gitsrc.text_diff(cfg, text)
            elif rev_range:
                b, _, h = rev_range.partition("...")
                diff = gitsrc.range_diff(cfg, b, h or "HEAD")
            elif source == "staged":
                diff = gitsrc.staged_diff(cfg)
            else:
                diff = gitsrc.worktree_diff(cfg, base=base)
    except RulewardenError as exc:
        from rulewarden.engine.runner import _synthetic

        res = Result(fatal=True)
        res.errors.append(str(exc))
        res.findings.append(
            _synthetic(
                "RW-DIFF",
                "critical",
                "change could not be read",
                "fix the repository state; failing closed",
                detail=str(exc)[:300],
                kind="error",
            )
        )
        emit(res, cfg, fmt, style, show_all, json_out)
        sys.exit(res.exit_code)
    req = Request(
        diff=diff, command=command, as_of=as_of.date() if isinstance(as_of, datetime) else as_of
    )
    result = run_check(cfg, req)
    emit(result, cfg, fmt, style, show_all, json_out)
    if not no_audit:
        try:
            audit.append(
                cfg.root,
                result,
                audit.Event(
                    harness=harness, event="check", elapsed_ms=int((time.monotonic() - t0) * 1000)
                ),
            )
        except OSError as exc:
            click.echo(f"warning: audit log not written: {exc}", err=True)
    sys.exit(result.exit_code)


@main.command("test-rules")
@click.option("--root", type=click.Path(file_okay=False))
@click.option(
    "--path",
    "paths",
    multiple=True,
    help="Rule file or directory (default: configured rule paths).",
)
@click.option("--verbose", "-v", is_flag=True)
def test_rules(root: str | None, paths: tuple[str, ...], verbose: bool) -> None:
    """Run every rule's fixtures (tool qualification, P6)."""
    from dataclasses import replace

    from rulewarden.engine.fixtures import qualify
    from rulewarden.engine.loader import load_rules

    cfg = _config(root)
    if paths:
        cfg = replace(cfg, rule_paths=paths)
    try:
        rs = load_rules(cfg)
    except RulewardenError as exc:
        click.echo(f"ERROR — {exc}", err=True)
        sys.exit(EXIT_ERROR)
    rep = qualify(cfg, rs)
    for o in rep.outcomes:
        if verbose or not o.ok:
            mark = "ok  " if o.ok else "FAIL"
            click.echo(f"{mark} {o.rule_id} {o.expected}[{o.index}] {o.detail}".rstrip())
    s = rep.summary()
    undecidable = sum(1 for pr in rs.rules if pr.rule.check is None)
    click.echo(
        f"{'PASS' if rep.passed else 'FAIL'} — {s['fixtures']} fixtures across {s['rules']} rules"
        f" ({undecidable} undecidable rules listed, not evaluated)"
    )
    sys.exit(0 if rep.passed else 1)


@main.command()
@click.option("--root", type=click.Path(file_okay=False))
@click.option(
    "--ci",
    "noninteractive",
    is_flag=True,
    help="Allow running without a TTY (scripted setup by a human).",
)
@click.option(
    "--check",
    "verify_only",
    is_flag=True,
    help="Only verify the existing lock; exit 1 if it is stale.",
)
def lock(root: str | None, noninteractive: bool, verify_only: bool) -> None:
    """Qualify the rule set and write rules.lock (a human action; hooks block agents from running it)."""
    from rulewarden.engine.fixtures import qualify
    from rulewarden.engine.loader import load_rules
    from rulewarden.engine.lock import build_lock, verify_lock, write_lock

    cfg = _config(root)
    if verify_only:
        try:
            verify_lock(cfg)
        except RulewardenError as exc:
            click.echo(f"STALE — {exc}")
            sys.exit(1)
        click.echo("OK — rules.lock matches the rule set")
        return
    if not noninteractive and not sys.stdin.isatty():
        click.echo(
            "ERROR — `rulewarden lock` is a human action and needs an interactive terminal (or --ci in human-run scripts).",
            err=True,
        )
        sys.exit(EXIT_ERROR)
    try:
        rs = load_rules(cfg)
    except RulewardenError as exc:
        click.echo(f"ERROR — {exc}", err=True)
        sys.exit(EXIT_ERROR)
    rep = qualify(cfg, rs)
    if not rep.passed:
        for o in rep.failures:
            click.echo(f"FAIL {o.rule_id} {o.expected}[{o.index}] {o.detail}", err=True)
        click.echo(
            "ERROR — fixtures failed; refusing to lock an unqualified rule set (P6)", err=True
        )
        sys.exit(1)
    data = build_lock(cfg, rs, rep.summary())
    path = write_lock(cfg, data)
    n_prot = len(data["protected"])  # type: ignore[arg-type]
    n_dev = len(data["deviations"])  # type: ignore[arg-type]
    click.echo(
        f"locked {len(rs.rules)} rules, {n_prot} protected files, {n_dev} registered deviations → {path.name}"
    )


@main.command()
@click.option("--root", type=click.Path(file_okay=False))
@click.option("--determinism-only", is_flag=True, help="Run only the determinism self-test.")
def doctor(root: str | None, determinism_only: bool) -> None:
    """Verify installation, hook wiring, lock integrity and determinism."""
    from rulewarden.doctor import run_doctor

    cfg = _config(root)
    ok, lines = run_doctor(cfg, determinism_only=determinism_only)
    for line in lines:
        click.echo(line)
    sys.exit(0 if ok else 1)


def _json_dump(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False)


@main.command()
@click.argument(
    "harness",
    type=click.Choice(["claude-code", "git", "pre-commit", "ci", "codex", "gemini", "opencode"]),
)
@click.argument("args", nargs=-1)
@click.option("--root", type=click.Path(file_okay=False))
def hook(harness: str, args: tuple[str, ...], root: str | None) -> None:
    """Harness adapter entry point (reads the harness's JSON or git arguments)."""
    cfg = _config(root)
    if harness == "claude-code":
        from rulewarden.adapters import claude_code

        reply = claude_code.main(cfg, sys.stdin.read())
        if reply.exit_code == 2:
            click.echo(reply.stdout, err=True)
        elif reply.stdout:
            click.echo(reply.stdout)
        sys.exit(reply.exit_code)
    if harness in ("codex", "gemini", "opencode"):
        from rulewarden.adapters import other_harnesses

        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except ValueError as exc:
            click.echo(f"rulewarden: unreadable hook input ({exc}); failing closed", err=True)
            sys.exit(2)
        reply = getattr(other_harnesses, harness)(cfg, payload)
        if reply.stdout:
            click.echo(reply.stdout)
        sys.exit(0)
    if harness in ("git", "pre-commit"):
        from rulewarden.adapters import git_hook

        name = args[0] if args else "pre-commit"
        rest = args[1:] if args else ()
        stdin_text = sys.stdin.read() if name == "pre-push" else ""
        res, text = git_hook.run(cfg, name, rest, stdin_text)
        if res.findings:
            click.echo(text, err=True, nl=False)
        sys.exit(res.exit_code)
    from rulewarden.adapters import ci

    base = args[0] if args else os.environ.get("RULEWARDEN_BASE", "origin/main")
    res = ci.check_range(cfg, base, args[1] if len(args) > 1 else "HEAD")
    for line in ci.gh_annotations(res):
        click.echo(line)
    click.echo(render_text(res, cfg.report.style, 10**9, 0), nl=False)
    sys.exit(res.exit_code)


@main.command("compile")
@click.argument("instruction_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--root", type=click.Path(file_okay=False))
@click.option("--out", type=click.Path(dir_okay=False), help="Write proposed rules here (YAML).")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def compile_cmd(instruction_file: str, root: str | None, out: str | None, fmt: str) -> None:
    """Instruction file → rule proposals, plus every line that could not be compiled and why."""
    from dataclasses import asdict

    from rulewarden.compile.compiler import compile_file, report_text, to_yaml

    cfg = _config(root)
    res = compile_file(Path(instruction_file), cfg)
    if out:
        Path(out).write_text(to_yaml(res), encoding="utf-8")
    if fmt == "json":
        click.echo(
            _json_dump(
                {
                    "source": res.source,
                    "counts": res.counts(),
                    "lines": [asdict(ln) for ln in res.lines],
                    "rules": res.rules,
                }
            )
        )
    else:
        click.echo(report_text(res), nl=False)
        if not out:
            click.echo(to_yaml(res), nl=False)


INSTRUCTION_FILES = (
    ("CLAUDE.md", "CL"),
    ("AGENTS.md", "AG"),
    (".cursorrules", "CR"),
    ("GEMINI.md", "GE"),
    (".windsurfrules", "WS"),
)
PACKS = (
    "protected-set",
    "scope",
    "secrets",
    "no-answer-embedding",
    "hygiene-python",
    "shell-tooling",
    "voice",
)


@main.command()
@click.option("--root", type=click.Path(file_okay=False))
@click.option(
    "--packs",
    default=",".join(PACKS),
    show_default=True,
    help="Comma-separated starter packs to vendor.",
)
@click.option(
    "--claude/--no-claude",
    default=True,
    help="Install Claude Code hooks into .claude/settings.json.",
)
@click.option("--git-hooks/--no-git-hooks", default=True, help="Install plain git hooks.")
@click.option("--opencode", is_flag=True, help="Install the OpenCode plugin.")
@click.option("--binary", help="Path of the rulewarden executable the hooks call.")
@click.option(
    "--lock/--no-lock",
    "do_lock",
    default=False,
    help="Also lock (human action; needs a TTY or --ci).",
)
@click.option(
    "--hooks-only",
    is_flag=True,
    help="Only install hooks (after locking); do not vendor packs or compile.",
)
def init(
    root: str | None,
    packs: str,
    claude: bool,
    git_hooks: bool,
    opencode: bool,
    binary: str | None,
    do_lock: bool,
    hooks_only: bool,
) -> None:
    """Detect instruction files, vendor packs, compile rules, install hooks.

    Agent-harness hooks (Claude Code, OpenCode) are installed only together with
    --lock, between two lock writes, so they never run without a lock (ADR-013).
    """
    from rulewarden.adapters import claude_code, git_hook
    from rulewarden.adapters.other_harnesses import OPENCODE_PLUGIN

    cfg = _config(root)
    bin_path = binary or git_hook.default_binary(cfg.root)
    if not hooks_only:
        _scaffold(cfg, packs)
    if git_hooks:
        for p in git_hook.install(cfg.root, bin_path):
            click.echo(f"installed git hook {p.name}")
    agent_hooks = claude or opencode
    if not do_lock:
        if agent_hooks:
            click.echo("agent hooks not installed: they deny every tool call until a lock exists")
            click.echo(
                "next: review rules/, then a human runs `rulewarden init --hooks-only --lock`"
            )
        else:
            click.echo("next: review rules/, then a human runs `rulewarden lock`")
        return
    ctx = click.get_current_context()
    noninteractive = not sys.stdin.isatty()
    ctx.invoke(lock, root=str(cfg.root), noninteractive=noninteractive, verify_only=False)
    if not agent_hooks:
        return
    if claude:
        settings = cfg.root / ".claude" / "settings.json"
        settings.parent.mkdir(exist_ok=True)
        existing = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else {}
        settings.write_text(
            _json_dump(claude_code.merge_settings(existing, bin_path)) + "\n", encoding="utf-8"
        )
        click.echo("installed Claude Code hooks in .claude/settings.json")
    if opencode:
        d = cfg.root / ".opencode" / "plugins"
        d.mkdir(parents=True, exist_ok=True)
        (d / "rulewarden.js").write_text(
            OPENCODE_PLUGIN.replace("{bin}", bin_path), encoding="utf-8"
        )
        click.echo("installed OpenCode plugin")
    # The hook files are protected paths, so the lock must also record them.
    ctx.invoke(lock, root=str(cfg.root), noninteractive=noninteractive, verify_only=False)


def _scaffold(cfg: Config, packs: str) -> None:
    from importlib import resources

    from rulewarden.compile.compiler import compile_file, report_text, to_yaml
    from rulewarden.compile.templates import pack_rules

    rules_dir = cfg.root / "rules"
    (rules_dir / "packs").mkdir(parents=True, exist_ok=True)
    for name in [p.strip() for p in packs.split(",") if p.strip()]:
        src = resources.files("rulewarden.packs") / f"{name}.yaml"
        if not src.is_file():
            click.echo(f"unknown pack {name!r}", err=True)
            sys.exit(EXIT_ERROR)
        (rules_dir / "packs" / f"{name}.yaml").write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8"
        )
        click.echo(f"vendored pack {name}")
    vendored = [p.strip() for p in packs.split(",") if p.strip()]
    vendored_ids = {rid for rid, body in pack_rules().items() if body.get("pack_name") in vendored}
    for candidate, prefix in INSTRUCTION_FILES:
        p = cfg.root / candidate
        if not p.is_file():
            continue
        res = compile_file(p, cfg, prefix=prefix)
        novel = [
            r
            for r in res.rules
            if not any(t.removeprefix("from-pack:") in vendored_ids for t in r.get("tags", []))
        ]
        click.echo(report_text(res), nl=False)
        if novel:
            res.rules = novel
            target = rules_dir / f"compiled-{candidate.lstrip('.').replace('.', '-').lower()}.yaml"
            target.write_text(to_yaml(res), encoding="utf-8")
            click.echo(
                f"wrote {len(novel)} project-specific rules to {target.relative_to(cfg.root)}"
            )
    (cfg.root / ".rulewarden").mkdir(exist_ok=True)
    gi = cfg.root / ".gitignore"
    lines = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    for entry in (".rulewarden/audit.jsonl", ".rulewarden/session.json", ".rulewarden/tmp/"):
        if entry not in lines:
            lines.append(entry)
    gi.write_text("\n".join(lines) + "\n", encoding="utf-8")


@main.command()
@click.option("--root", type=click.Path(file_okay=False))
@click.option("--format", "fmt", type=click.Choice(["markdown", "json"]), default="markdown")
@click.option(
    "--framework",
    type=click.Choice(["nist-ai-rmf"]),
    help="Map the evidence to a governance framework (v3).",
)
@click.option("--limit", type=int, default=50, help="Most recent audit entries to list.")
def report(root: str | None, fmt: str, framework: str | None, limit: int) -> None:
    """Render the audit log (and optionally a framework evidence summary)."""
    from rulewarden.reporting import framework_summary, render_audit

    cfg = _config(root)
    click.echo(
        render_audit(cfg, fmt, limit)
        if framework is None
        else framework_summary(cfg, framework, fmt),
        nl=False,
    )


@main.command()
@click.option("--root", type=click.Path(file_okay=False))
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def stats(root: str | None, fmt: str) -> None:
    """Near-miss and self-correction metrics from the audit log (P10)."""
    from rulewarden.reporting import compute_stats, render_stats

    cfg = _config(root)
    s = compute_stats(cfg)
    click.echo(_json_dump(s) + "\n" if fmt == "json" else render_stats(s), nl=False)
