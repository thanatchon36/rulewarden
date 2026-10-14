"""Check engines. Each module exposes prepare(params, on, ctx) and run(prepared, on, target, ctx)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from rulewarden.config import Limits
from rulewarden.engine.diff import AddedBlock
from rulewarden.engine.schema import EngineName, On


@dataclass(frozen=True)
class Hit:
    line: int | None
    detail: str = ""
    unverifiable: bool = False


@dataclass
class Target:
    path: str
    status: str = "modified"
    content: str | None = None
    added: list[tuple[int, str]] = field(default_factory=list)
    blocks: list[AddedBlock] = field(default_factory=list)
    command: str | None = None
    changeset: tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineContext:
    root: Path
    limits: Limits
    allow_shell: bool = False
    shell_allowlist: tuple[str, ...] = ()
    protected: tuple[str, ...] = ()


Prepare = Callable[[Mapping[str, Any], On, EngineContext], Any]
Run = Callable[[Any, On, Target, EngineContext], list[Hit]]


def _modules() -> dict[EngineName, ModuleType]:
    from rulewarden.engine.checks import (
        ast_check,
        glob_check,
        jq_check,
        python_check,
        regex_check,
        shell_check,
    )

    return {
        EngineName.REGEX: regex_check,
        EngineName.GLOB: glob_check,
        EngineName.AST: ast_check,
        EngineName.JQ: jq_check,
        EngineName.SHELL: shell_check,
        EngineName.PYTHON: python_check,
    }


def engine(name: EngineName) -> ModuleType:
    return _modules()[name]


def require_keys(
    params: Mapping[str, Any], allowed: set[str], required: set[str], where: str
) -> None:
    from rulewarden.errors import SchemaError

    unknown = set(params) - allowed
    if unknown:
        raise SchemaError(f"{where}: unknown check keys {sorted(unknown)}")
    missing = required - set(params)
    if missing:
        raise SchemaError(f"{where}: missing check keys {sorted(missing)}")
