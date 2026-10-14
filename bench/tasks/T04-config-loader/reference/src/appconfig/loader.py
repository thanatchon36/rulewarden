import configparser
import os
import re
from collections.abc import Mapping
from pathlib import Path

_VAR = re.compile(r"\$\$|\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_INT = re.compile(r"[+-]?\d+")
_FLOAT = re.compile(r"[+-]?(\d+\.\d*|\.\d+)([eE][+-]?\d+)?")
_BOOLS = {"true": True, "yes": True, "on": True, "false": False, "no": False, "off": False}


def _interpolate(value: str, env: Mapping[str, str]) -> str:
    def sub(m: re.Match[str]) -> str:
        if m.group(0) == "$$":
            return "$"
        name = m.group(1)
        if name not in env:
            raise KeyError(name)
        return env[name]

    return _VAR.sub(sub, value)


def _convert(value: str) -> object:
    text = value.strip()
    if text.lower() in _BOOLS:
        return _BOOLS[text.lower()]
    if _INT.fullmatch(text):
        return int(text)
    if _FLOAT.fullmatch(text):
        return float(text)
    return text


def load_config(path: str | Path, env: Mapping[str, str] | None = None) -> dict[str, dict[str, object]]:
    """Read an INI file into typed values, with ${VAR} interpolation and APP_* overrides."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    env = os.environ if env is None else env
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(p.read_text(encoding="utf-8"))
    out: dict[str, dict[str, object]] = {}
    for section in parser.sections():
        values: dict[str, object] = {}
        for key, raw in parser.items(section):
            override = env.get(f"APP_{section.upper()}_{key.upper()}")
            values[key] = _convert(override if override is not None else _interpolate(raw, env))
        out[section] = values
    return out
