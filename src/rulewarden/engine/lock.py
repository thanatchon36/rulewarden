"""rules.lock: a human-issued certificate over the rule set, protected files and approved deviations (P2, P6)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from rulewarden import __version__
from rulewarden.config import APPROVERS_FILE, CONFIG_FILE, PLUGIN_DIR, RUNTIME_FILES, Config
from rulewarden.engine import deviations as dev
from rulewarden.engine.globs import match_any
from rulewarden.engine.loader import RuleSet, rule_files
from rulewarden.errors import LockError

LOCK_VERSION = 1


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash(path: Path) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError:
        return None


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class Lock:
    ruleset_sha256: str
    rules: dict[str, str]
    protected: dict[str, str]
    deviations: frozenset[str]
    qualification: dict[str, object] = field(default_factory=dict)


def _rel(p: Path, root: Path) -> str:
    return p.resolve().relative_to(root.resolve()).as_posix()


def ruleset_inputs(config: Config) -> dict[str, str]:
    """Every file whose content defines enforcement behaviour: rules, config, approvers, plugins."""
    root = config.root
    files = list(rule_files(config))
    for extra in (CONFIG_FILE, APPROVERS_FILE):
        if (root / extra).is_file():
            files.append(root / extra)
    plugdir = root / PLUGIN_DIR
    if plugdir.is_dir():
        files.extend(p for p in plugdir.rglob("*.py") if p.is_file())
    out: dict[str, str] = {}
    for f in sorted(set(files), key=lambda q: q.as_posix()):
        h = _hash(f)
        if h is not None:
            out[_rel(f, root)] = h
    return out


def ruleset_sha256(inputs: dict[str, str]) -> str:
    return sha256_bytes(canonical(inputs).encode("utf-8"))


def candidate_files(root: Path) -> list[str]:
    from rulewarden.engine.gitsrc import git

    try:
        out = git(root, "ls-files", "-co", "--exclude-standard", "-z")
        return sorted(p for p in out.split("\0") if p)
    except Exception:  # noqa: BLE001 - not a git repo: fall back to a walk
        skip = {".git", ".venv", "node_modules", "__pycache__"}
        res = []
        for p in root.rglob("*"):
            if p.is_file() and not (set(p.relative_to(root).parts) & skip):
                res.append(p.relative_to(root).as_posix())
        return sorted(res)


def protected_files(config: Config) -> dict[str, str]:
    root = config.root
    out: dict[str, str] = {}
    for rel in candidate_files(root):
        if rel == config.lock_file or match_any(rel, RUNTIME_FILES):
            continue
        if match_any(rel, config.protected_paths):
            h = _hash(root / rel)
            if h is not None:
                out[rel] = h
    return out


def blocking_deviations(config: Config, ruleset: RuleSet) -> list[dev.Deviation]:
    blocking_ids = {pr.rule.id for pr in ruleset.rules if pr.rule.severity.blocking}
    found: list[dev.Deviation] = []
    for rel in candidate_files(config.root):
        p = config.root / rel
        try:
            if p.stat().st_size > config.limits.max_file_bytes:
                continue
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found.extend(
            d for d in dev.scan(rel, text) if d.rule_id in blocking_ids and not d.malformed
        )
    return found


def build_lock(
    config: Config, ruleset: RuleSet, qualification: dict[str, object]
) -> dict[str, object]:
    inputs = ruleset_inputs(config)
    return {
        "version": LOCK_VERSION,
        "rulewarden": __version__,
        "ruleset_sha256": ruleset_sha256(inputs),
        "rules": inputs,
        "protected": protected_files(config),
        "deviations": sorted({d.fingerprint for d in blocking_deviations(config, ruleset)}),
        "qualification": qualification,
    }


def write_lock(config: Config, data: dict[str, object]) -> Path:
    path = config.root / config.lock_file
    path.write_text(
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def read_lock(config: Config) -> Lock:
    path = config.root / config.lock_file
    if not path.exists():
        raise LockError(
            f"{config.lock_file} not found; a human must review the rules and run `rulewarden lock`"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LockError(f"{config.lock_file} is unreadable: {exc}") from exc
    try:
        if data["version"] != LOCK_VERSION:
            raise LockError(f"{config.lock_file}: unsupported version {data['version']!r}")
        return Lock(
            ruleset_sha256=str(data["ruleset_sha256"]),
            rules=dict(data["rules"]),
            protected=dict(data.get("protected", {})),
            deviations=frozenset(data.get("deviations", [])),
            qualification=dict(data.get("qualification", {})),
        )
    except (KeyError, TypeError) as exc:
        raise LockError(f"{config.lock_file} is malformed: {exc}") from exc


def verify_lock(config: Config) -> Lock:
    """Return the lock if the current rule inputs match it exactly; raise LockError otherwise."""
    lock = read_lock(config)
    current = ruleset_inputs(config)
    if ruleset_sha256(current) != lock.ruleset_sha256 or current != lock.rules:
        changed = sorted(set(current.items()) ^ set(lock.rules.items()))
        names = sorted({k for k, _ in changed})
        raise LockError(
            "rule set differs from rules.lock ("
            + ", ".join(names[:5])
            + (", …" if len(names) > 5 else "")
            + ")"
        )
    return lock
