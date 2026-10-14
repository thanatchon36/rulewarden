"""Rule schema: the single source of truth for what a rule file may contain (MISSION §4.2)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any

from rulewarden.errors import SchemaError

RULE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$")
SCHEMA_VERSION = 1


class Severity(StrEnum):
    ADVISORY = "advisory"
    REQUIRED = "required"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {"critical": 0, "required": 1, "advisory": 2}[self.value]

    @property
    def blocking(self) -> bool:
        return self is not Severity.ADVISORY


class Decidability(StrEnum):
    DETERMINISTIC = "deterministic"
    HEURISTIC = "heuristic"
    UNDECIDABLE = "undecidable"


class Scope(StrEnum):
    DIFF = "diff"
    FILE = "file"
    REPO = "repo"
    COMMAND = "command"


class EngineName(StrEnum):
    REGEX = "regex"
    GLOB = "glob"
    AST = "ast"
    JQ = "jq"
    SHELL = "shell"
    PYTHON = "python"


class On(StrEnum):
    ADDED_LINES = "added_lines"
    HUNKS = "hunks"
    FILE = "file"
    PATH = "path"
    COMMAND = "command"


@dataclass(frozen=True)
class Check:
    engine: EngineName
    on: On
    params: Mapping[str, Any]


@dataclass(frozen=True)
class Fixtures:
    fail: tuple[Any, ...]
    pass_: tuple[Any, ...]


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    severity: Severity
    decidability: Decidability
    scope: Scope
    applies_to: tuple[str, ...]
    exclude: tuple[str, ...]
    check: Check | None
    message: str
    fixtures: Fixtures | None
    deviations_allowed: bool
    source: str | None
    tags: tuple[str, ...]
    origin: str = field(default="", compare=False)

    @property
    def blocking(self) -> bool:
        return self.decidability is Decidability.DETERMINISTIC and self.severity.blocking


_RULE_KEYS = {
    "id",
    "title",
    "source",
    "severity",
    "decidability",
    "scope",
    "applies_to",
    "exclude",
    "check",
    "message",
    "fixtures",
    "deviations",
    "tags",
}
_REQUIRED_KEYS = {"id", "title", "severity", "decidability", "message"}
_DEFAULT_ON = {
    EngineName.REGEX: On.ADDED_LINES,
    EngineName.GLOB: On.PATH,
    EngineName.AST: On.FILE,
    EngineName.JQ: On.FILE,
    EngineName.SHELL: On.FILE,
    EngineName.PYTHON: On.FILE,
}
_ALLOWED_ON = {
    EngineName.REGEX: {On.ADDED_LINES, On.HUNKS, On.FILE, On.COMMAND, On.PATH},
    EngineName.GLOB: {On.PATH},
    EngineName.AST: {On.FILE},
    EngineName.JQ: {On.FILE},
    EngineName.SHELL: {On.FILE, On.COMMAND},
    EngineName.PYTHON: {On.FILE, On.ADDED_LINES, On.COMMAND},
}


def _enum(cls: type[Enum], value: object, where: str) -> Any:
    try:
        return cls(value)
    except ValueError:
        allowed = ", ".join(str(m.value) for m in cls)
        raise SchemaError(f"{where}: {value!r} is not one of: {allowed}") from None


def _str_list(value: object, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, Sequence) or not all(isinstance(v, str) for v in value):
        raise SchemaError(f"{where}: expected a list of strings")
    return tuple(value)


def _nonempty_str(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{where}: expected a non-empty string")
    return value


def parse_check(raw: object, where: str) -> Check:
    if not isinstance(raw, Mapping):
        raise SchemaError(f"{where}.check: expected a mapping")
    if True in raw:  # YAML 1.1 reads the bare key `on` as boolean true
        raw = {("on" if k is True else k): v for k, v in raw.items()}
    bad = [k for k in raw if not isinstance(k, str)]
    if bad:
        raise SchemaError(f"{where}.check: non-string keys {bad!r}")
    engine = _enum(EngineName, raw.get("engine"), f"{where}.check.engine")
    on = _enum(On, raw.get("on", _DEFAULT_ON[engine].value), f"{where}.check.on")
    if on not in _ALLOWED_ON[engine]:
        raise SchemaError(
            f"{where}.check.on: {on.value!r} is not valid for engine {engine.value!r}"
        )
    params = {k: v for k, v in raw.items() if k not in ("engine", "on")}
    return Check(engine=engine, on=on, params=params)


def parse_fixtures(raw: object, where: str) -> Fixtures:
    if not isinstance(raw, Mapping):
        raise SchemaError(f"{where}.fixtures: expected a mapping with 'fail' and 'pass' lists")
    unknown = set(raw) - {"fail", "pass"}
    if unknown:
        raise SchemaError(f"{where}.fixtures: unknown keys {sorted(unknown)}")
    fail = raw.get("fail")
    pass_ = raw.get("pass")
    if not isinstance(fail, list) or not fail:
        raise SchemaError(f"{where}.fixtures.fail: at least one failing fixture is required (P6)")
    if not isinstance(pass_, list) or not pass_:
        raise SchemaError(f"{where}.fixtures.pass: at least one passing fixture is required (P6)")
    return Fixtures(fail=tuple(fail), pass_=tuple(pass_))


def parse_rule(raw: object, origin: str = "") -> Rule:
    if not isinstance(raw, Mapping):
        raise SchemaError(f"{origin}: each rule must be a mapping")
    rid = raw.get("id")
    where = f"{origin}:{rid}" if rid else f"{origin}:<rule without id>"
    unknown = set(raw) - _RULE_KEYS
    if unknown:
        raise SchemaError(f"{where}: unknown keys {sorted(unknown)}")
    missing = _REQUIRED_KEYS - set(raw)
    if missing:
        raise SchemaError(f"{where}: missing keys {sorted(missing)}")
    rid = _nonempty_str(rid, f"{where}.id")
    if not RULE_ID_RE.match(rid):
        raise SchemaError(f"{where}.id: must match {RULE_ID_RE.pattern}")
    severity = _enum(Severity, raw["severity"], f"{where}.severity")
    decidability = _enum(Decidability, raw["decidability"], f"{where}.decidability")
    if decidability is Decidability.HEURISTIC and severity is not Severity.ADVISORY:
        raise SchemaError(
            f"{where}: heuristic rules may only be advisory (P3: only deterministic rules block)"
        )
    scope = _enum(Scope, raw.get("scope", "diff"), f"{where}.scope")
    deviations = raw.get("deviations", "allowed")
    if deviations not in ("allowed", "forbidden"):
        raise SchemaError(f"{where}.deviations: must be 'allowed' or 'forbidden'")
    source = raw.get("source")
    if source is not None and not isinstance(source, str):
        raise SchemaError(f"{where}.source: expected a string")

    check: Check | None = None
    fixtures: Fixtures | None = None
    if decidability is Decidability.UNDECIDABLE:
        if raw.get("check") is not None:
            raise SchemaError(
                f"{where}: undecidable rules are never evaluated and must not have a check (P3)"
            )
    else:
        if raw.get("check") is None:
            raise SchemaError(f"{where}: missing check")
        check = parse_check(raw["check"], where)
        fixtures = parse_fixtures(raw.get("fixtures"), where)
        if scope is Scope.COMMAND and check.on is not On.COMMAND:
            raise SchemaError(f"{where}: scope 'command' requires check.on 'command'")
        if check.on is On.COMMAND and scope is not Scope.COMMAND:
            raise SchemaError(f"{where}: check.on 'command' requires scope 'command'")

    return Rule(
        id=rid,
        title=_nonempty_str(raw["title"], f"{where}.title"),
        severity=severity,
        decidability=decidability,
        scope=scope,
        applies_to=_str_list(raw.get("applies_to"), f"{where}.applies_to") or ("**",),
        exclude=_str_list(raw.get("exclude"), f"{where}.exclude"),
        check=check,
        message=_nonempty_str(raw["message"], f"{where}.message"),
        fixtures=fixtures,
        deviations_allowed=deviations == "allowed",
        source=source,
        tags=_str_list(raw.get("tags"), f"{where}.tags"),
        origin=origin,
    )


def parse_rule_file(data: object, origin: str) -> list[Rule]:
    if not isinstance(data, Mapping):
        raise SchemaError(f"{origin}: top level must be a mapping with 'version' and 'rules'")
    unknown = set(data) - {"version", "rules", "pack", "description"}
    if unknown:
        raise SchemaError(f"{origin}: unknown top-level keys {sorted(unknown)}")
    if data.get("version") != SCHEMA_VERSION:
        raise SchemaError(f"{origin}: version must be {SCHEMA_VERSION}")
    rules = data.get("rules")
    if not isinstance(rules, list):
        raise SchemaError(f"{origin}: 'rules' must be a list")
    return [parse_rule(r, origin) for r in rules]
