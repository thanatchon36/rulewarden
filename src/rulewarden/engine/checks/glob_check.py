"""Path policy: forbid changes to matching paths, or allow only matching paths."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from rulewarden.engine.checks import EngineContext, Hit, Target, require_keys
from rulewarden.engine.globs import match_any
from rulewarden.engine.schema import On
from rulewarden.errors import SchemaError

_KEYS = {"paths", "paths_from", "mode", "change", "exempt_if_locked", "unless_changed", "detail"}
_CHANGES = ("added", "modified", "deleted", "renamed")


@dataclass(frozen=True)
class Prepared:
    paths: tuple[str, ...]
    use_protected: bool
    mode: str
    change: frozenset[str]
    exempt_if_locked: bool
    detail: str
    unless_changed: tuple[str, ...] = ()


def prepare(params: Mapping[str, Any], on: On, ctx: EngineContext) -> Prepared:
    require_keys(params, _KEYS, set(), "glob")
    paths = params.get("paths", [])
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise SchemaError("glob: paths must be a list of globs")
    paths_from = params.get("paths_from")
    if paths_from not in (None, "protected"):
        raise SchemaError("glob: paths_from may only be 'protected'")
    if not paths and paths_from is None:
        raise SchemaError("glob: 'paths' or 'paths_from' is required")
    mode = params.get("mode", "forbid")
    if mode not in ("forbid", "allow"):
        raise SchemaError("glob: mode must be 'forbid' or 'allow'")
    change = params.get("change", list(_CHANGES))
    if isinstance(change, str):
        change = [change]
    if not isinstance(change, list) or not set(change) <= set(_CHANGES) or not change:
        raise SchemaError(f"glob: change must be a non-empty subset of {list(_CHANGES)}")
    exempt = params.get("exempt_if_locked", False)
    if not isinstance(exempt, bool):
        raise SchemaError("glob: exempt_if_locked must be a boolean")
    return Prepared(
        paths=tuple(paths),
        use_protected=paths_from == "protected",
        mode=mode,
        change=frozenset(change),
        exempt_if_locked=exempt,
        detail=str(params.get("detail", "")),
        unless_changed=_globs(params.get("unless_changed", [])),
    )


def _globs(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise SchemaError("glob: unless_changed must be a list of globs")
    return tuple(value)


def patterns(prep: Prepared, ctx: EngineContext) -> tuple[str, ...]:
    return prep.paths + (ctx.protected if prep.use_protected else ())


def run(prep: Prepared, on: On, target: Target, ctx: EngineContext) -> list[Hit]:
    if target.status not in prep.change:
        return []
    if prep.unless_changed and any(match_any(p, prep.unless_changed) for p in target.changeset):
        return []
    matched = match_any(target.path, patterns(prep, ctx))
    if (prep.mode == "forbid") == matched:
        detail = prep.detail or f"{target.status} {target.path}"
        return [Hit(None, detail)]
    return []
