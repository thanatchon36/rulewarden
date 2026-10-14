"""Python plugin engine. Built-ins live in rulewarden.plugins; local plugins only under .rulewarden/plugins/."""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rulewarden.config import PLUGIN_DIR
from rulewarden.engine.checks import EngineContext, Hit, Target, require_keys
from rulewarden.engine.schema import On
from rulewarden.errors import EngineError, SchemaError

_KEYS = {"plugin", "options", "detail"}
PluginFn = Callable[[Target, Mapping[str, Any]], list[Hit]]


@dataclass(frozen=True)
class Prepared:
    fn: PluginFn
    options: Mapping[str, Any]
    name: str


def _resolve_builtin(name: str) -> PluginFn:
    dotted = name.removeprefix("packs.")
    mod_name, _, fn_name = dotted.rpartition(".")
    if not mod_name:
        raise SchemaError(f"python: plugin {name!r} must be '<module>.<function>'")
    try:
        mod = importlib.import_module(f"rulewarden.plugins.{mod_name}")
    except ImportError as exc:
        raise SchemaError(f"python: unknown built-in plugin module {mod_name!r}") from exc
    fn = getattr(mod, fn_name, None)
    if not callable(fn) or fn_name.startswith("_"):
        raise SchemaError(f"python: plugin {name!r} not found")
    return fn  # type: ignore[no-any-return]


def _resolve_local(spec: str, root: Path) -> PluginFn:
    rel, _, fn_name = spec.removeprefix("local:").rpartition(":")
    base = (root / PLUGIN_DIR).resolve()
    path = (base / rel).resolve()
    if base not in path.parents or path.suffix != ".py" or not path.is_file():
        raise SchemaError(
            f"python: local plugins must be .py files under {PLUGIN_DIR}/ (got {rel!r})"
        )
    module_spec = importlib.util.spec_from_file_location(f"rulewarden_local_{path.stem}", path)
    if module_spec is None or module_spec.loader is None:
        raise SchemaError(f"python: cannot load {rel!r}")
    mod = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(mod)
    fn = getattr(mod, fn_name, None)
    if not callable(fn):
        raise SchemaError(f"python: function {fn_name!r} not found in {rel!r}")
    return fn  # type: ignore[no-any-return]


def prepare(params: Mapping[str, Any], on: On, ctx: EngineContext) -> Prepared:
    require_keys(params, _KEYS, {"plugin"}, "python")
    name = params["plugin"]
    if not isinstance(name, str):
        raise SchemaError("python: plugin must be a string")
    options = params.get("options", {})
    if not isinstance(options, Mapping):
        raise SchemaError("python: options must be a mapping")
    fn = _resolve_local(name, ctx.root) if name.startswith("local:") else _resolve_builtin(name)
    return Prepared(fn=fn, options=dict(options), name=name)


def run(prep: Prepared, on: On, target: Target, ctx: EngineContext) -> list[Hit]:
    try:
        result = prep.fn(target, prep.options)
    except Exception as exc:
        raise EngineError(f"python plugin {prep.name} failed: {type(exc).__name__}: {exc}") from exc
    if not isinstance(result, list) or not all(isinstance(h, Hit) for h in result):
        raise EngineError(f"python plugin {prep.name} must return a list of Hit")
    return result
