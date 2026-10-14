"""Load rule files, validate them, and prepare each check engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rulewarden.config import Config
from rulewarden.engine.checks import EngineContext, engine
from rulewarden.engine.schema import Rule, parse_rule_file
from rulewarden.errors import LoadError, SchemaError

MAX_RULE_FILE_BYTES = 1_000_000
RULE_SUFFIXES = (".yaml", ".yml")


@dataclass(frozen=True)
class PreparedRule:
    rule: Rule
    prepared: Any


@dataclass(frozen=True)
class RuleSet:
    rules: tuple[PreparedRule, ...]
    files: tuple[str, ...]

    @property
    def by_id(self) -> dict[str, PreparedRule]:
        return {pr.rule.id: pr for pr in self.rules}

    @property
    def digest(self) -> str:
        import hashlib

        text = "\n".join(repr(pr.rule) for pr in self.rules)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


def engine_context(config: Config) -> EngineContext:
    return EngineContext(
        root=config.root,
        limits=config.limits,
        allow_shell=config.allow_shell_engine,
        shell_allowlist=config.shell_allowlist,
        protected=config.protected_paths,
    )


def rule_files(config: Config) -> list[Path]:
    out: list[Path] = []
    for rel in config.rule_paths:
        p = (config.root / rel).resolve()
        if p.is_dir():
            out.extend(sorted(q for q in p.rglob("*") if q.is_file() and q.suffix in RULE_SUFFIXES))
        elif p.is_file():
            out.append(p)
        else:
            raise LoadError(f"rule path {rel!r} does not exist")
    return sorted(dict.fromkeys(out), key=lambda q: q.as_posix())


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_rule_text(text: str, origin: str) -> list[Rule]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SchemaError(f"{origin}: invalid YAML: {exc}") from exc
    return parse_rule_file(data, origin)


def prepare_rules(rules: list[Rule], ctx: EngineContext) -> tuple[PreparedRule, ...]:
    seen: dict[str, str] = {}
    out: list[PreparedRule] = []
    for r in rules:
        if r.id in seen:
            raise SchemaError(
                f"duplicate rule id {r.id} in {r.origin} (first defined in {seen[r.id]})"
            )
        seen[r.id] = r.origin
        prepared = None
        if r.check is not None:
            try:
                prepared = engine(r.check.engine).prepare(r.check.params, r.check.on, ctx)
            except SchemaError as exc:
                raise SchemaError(f"{r.origin}:{r.id}: {exc}") from exc
        out.append(PreparedRule(rule=r, prepared=prepared))
    return tuple(out)


def load_rules(config: Config) -> RuleSet:
    rules: list[Rule] = []
    files = rule_files(config)
    rels: list[str] = []
    for f in files:
        if f.stat().st_size > MAX_RULE_FILE_BYTES:
            raise LoadError(
                f"{_rel(f, config.root)}: rule file larger than {MAX_RULE_FILE_BYTES} bytes"
            )
        rel = _rel(f, config.root)
        rels.append(rel)
        rules.extend(load_rule_text(f.read_text(encoding="utf-8"), rel))
    return RuleSet(rules=prepare_rules(rules, engine_context(config)), files=tuple(rels))
