"""Project configuration (`.rulewarden/config.yaml`), with safe defaults when absent."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from rulewarden.errors import LoadError

CONFIG_DIR = ".rulewarden"
CONFIG_FILE = f"{CONFIG_DIR}/config.yaml"
APPROVERS_FILE = f"{CONFIG_DIR}/approvers"
AUDIT_FILE = f"{CONFIG_DIR}/audit.jsonl"
SESSION_FILE = f"{CONFIG_DIR}/session.json"
PLUGIN_DIR = f"{CONFIG_DIR}/plugins"

DEFAULT_PROTECTED: tuple[str, ...] = (
    "rules/**",
    "rules.lock",
    ".rulewarden/**",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".pre-commit-config.yaml",
    ".github/workflows/**",
    ".opencode/**",
    ".codex/**",
    ".gemini/**",
    ".git/hooks/**",
)
# Files under protected directories that rulewarden itself writes at runtime; they are git-ignored.
RUNTIME_FILES: tuple[str, ...] = (AUDIT_FILE, SESSION_FILE, f"{CONFIG_DIR}/tmp/**")


@dataclass(frozen=True)
class Limits:
    total_budget_s: float = 20.0
    per_check_s: float = 5.0
    max_diff_bytes: int = 20_000_000
    max_line_chars: int = 20_000
    max_file_bytes: int = 2_000_000


@dataclass(frozen=True)
class ReportConfig:
    advisory_cap: int = 5
    max_chars: int = 2000
    style: str = "managed"


@dataclass(frozen=True)
class Config:
    root: Path
    rule_paths: tuple[str, ...] = ("rules",)
    lock_file: str = "rules.lock"
    baseline: str = "HEAD"
    protected: tuple[str, ...] = DEFAULT_PROTECTED
    protect_package_source: bool = True
    allow_shell_engine: bool = False
    shell_allowlist: tuple[str, ...] = ()
    limits: Limits = field(default_factory=Limits)
    report: ReportConfig = field(default_factory=ReportConfig)
    raw: Mapping[str, Any] = field(default_factory=dict)

    @property
    def protected_paths(self) -> tuple[str, ...]:
        extra: tuple[str, ...] = ()
        if self.protect_package_source:
            extra = ("src/rulewarden/**",)
        return tuple(dict.fromkeys(self.protected + extra))


_KEYS = {
    "version",
    "rules",
    "lock",
    "baseline",
    "protected",
    "protect_package_source",
    "engines",
    "limits",
    "report",
}


def _typed(value: object, typ: type, where: str) -> Any:
    if typ is float and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, typ) or (typ is int and isinstance(value, bool)):
        raise LoadError(f"{CONFIG_FILE}: {where} must be {typ.__name__}")
    return value


def load_config(root: Path) -> Config:
    path = root / CONFIG_FILE
    if not path.exists():
        return Config(root=root)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise LoadError(f"{CONFIG_FILE}: invalid YAML: {exc}") from exc
    if not isinstance(data, Mapping):
        raise LoadError(f"{CONFIG_FILE}: top level must be a mapping")
    unknown = set(data) - _KEYS
    if unknown:
        raise LoadError(f"{CONFIG_FILE}: unknown keys {sorted(unknown)}")
    rules = data.get("rules", ["rules"])
    if isinstance(rules, str):
        rules = [rules]
    if not isinstance(rules, list) or not all(isinstance(r, str) for r in rules):
        raise LoadError(f"{CONFIG_FILE}: rules must be a list of paths")
    extra_protected = data.get("protected", [])
    if not isinstance(extra_protected, list) or not all(
        isinstance(p, str) for p in extra_protected
    ):
        raise LoadError(f"{CONFIG_FILE}: protected must be a list of globs")
    engines = data.get("engines", {}) or {}
    shell = engines.get("shell", {}) if isinstance(engines, Mapping) else {}
    if not isinstance(shell, Mapping):
        raise LoadError(f"{CONFIG_FILE}: engines.shell must be a mapping")
    lim_raw = data.get("limits", {}) or {}
    rep_raw = data.get("report", {}) or {}
    if not isinstance(lim_raw, Mapping) or not isinstance(rep_raw, Mapping):
        raise LoadError(f"{CONFIG_FILE}: limits/report must be mappings")
    d_lim = Limits()
    limits = Limits(
        total_budget_s=_typed(
            lim_raw.get("total_budget_s", d_lim.total_budget_s), float, "limits.total_budget_s"
        ),
        per_check_s=_typed(
            lim_raw.get("per_check_s", d_lim.per_check_s), float, "limits.per_check_s"
        ),
        max_diff_bytes=_typed(
            lim_raw.get("max_diff_bytes", d_lim.max_diff_bytes), int, "limits.max_diff_bytes"
        ),
        max_line_chars=_typed(
            lim_raw.get("max_line_chars", d_lim.max_line_chars), int, "limits.max_line_chars"
        ),
        max_file_bytes=_typed(
            lim_raw.get("max_file_bytes", d_lim.max_file_bytes), int, "limits.max_file_bytes"
        ),
    )
    d_rep = ReportConfig()
    style = rep_raw.get("style", d_rep.style)
    if style not in ("managed", "flat"):
        raise LoadError(f"{CONFIG_FILE}: report.style must be 'managed' or 'flat'")
    report = ReportConfig(
        advisory_cap=_typed(
            rep_raw.get("advisory_cap", d_rep.advisory_cap), int, "report.advisory_cap"
        ),
        max_chars=_typed(rep_raw.get("max_chars", d_rep.max_chars), int, "report.max_chars"),
        style=style,
    )
    allowlist = shell.get("allowlist", [])
    if not isinstance(allowlist, list) or not all(isinstance(a, str) for a in allowlist):
        raise LoadError(f"{CONFIG_FILE}: engines.shell.allowlist must be a list of binaries")
    return Config(
        root=root,
        rule_paths=tuple(rules),
        lock_file=_typed(data.get("lock", "rules.lock"), str, "lock"),
        baseline=_typed(data.get("baseline", "HEAD"), str, "baseline"),
        protected=tuple(dict.fromkeys(DEFAULT_PROTECTED + tuple(extra_protected))),
        protect_package_source=_typed(
            data.get("protect_package_source", True), bool, "protect_package_source"
        ),
        allow_shell_engine=_typed(shell.get("enabled", False), bool, "engines.shell.enabled"),
        shell_allowlist=tuple(allowlist),
        limits=limits,
        report=report,
        raw=data,
    )


def load_approvers(root: Path) -> frozenset[str]:
    path = root / APPROVERS_FILE
    if not path.exists():
        return frozenset()
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.split("#", 1)[0].strip()
        if s:
            names.append(s)
    return frozenset(names)
