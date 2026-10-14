from collections.abc import Mapping
from pathlib import Path


def load_config(path: str | Path, env: Mapping[str, str] | None = None) -> dict[str, dict[str, object]]:
    raise NotImplementedError
