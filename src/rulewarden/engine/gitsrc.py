"""Obtain diffs and file contents from git, deterministically (fixed locale, no pager, no ext diff)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from rulewarden.config import SESSION_FILE, Config
from rulewarden.engine.diff import Diff, FileChange, parse_diff, synthesize_added
from rulewarden.errors import BudgetExceeded, DiffError

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
_GIT_ENV = {
    "LC_ALL": "C",
    "LANG": "C",
    "GIT_PAGER": "cat",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_CONFIG_NOSYSTEM": "1",
}
_GIT_OPTS = [
    "-c",
    "core.quotepath=off",
    "-c",
    "color.ui=never",
    "-c",
    "diff.noprefix=false",
    "-c",
    "core.safecrlf=false",
]


def git(root: Path, *args: str, check: bool = True, input_text: str | None = None) -> str:
    env = {**os.environ, **_GIT_ENV}
    try:
        proc = subprocess.run(
            ["git", *_GIT_OPTS, *args],
            cwd=root,
            capture_output=True,
            env=env,
            input=input_text.encode("utf-8") if input_text is not None else None,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DiffError(f"git {' '.join(args)} failed: {exc}") from exc
    if check and proc.returncode != 0:
        raise DiffError(
            f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    return proc.stdout.decode("utf-8", errors="surrogateescape")


def repo_root(start: Path) -> Path:
    out = git(start, "rev-parse", "--show-toplevel")
    return Path(out.strip())


def has_commits(root: Path) -> bool:
    return bool(git(root, "rev-parse", "--verify", "-q", "HEAD", check=False).strip())


def resolve_base(root: Path, base: str) -> str:
    if base == "HEAD" and not has_commits(root):
        return EMPTY_TREE
    out = git(root, "rev-parse", "--verify", "-q", base + "^{tree}", check=False).strip()
    if not out:
        raise DiffError(f"baseline {base!r} does not resolve to a commit or tree")
    return base


def _diff_args(base_args: list[str]) -> list[str]:
    return ["diff", "--no-color", "--no-ext-diff", "--no-textconv", "-M", "-U0", *base_args]


def _cap(text: str, config: Config) -> str:
    if len(text.encode("utf-8", errors="surrogateescape")) > config.limits.max_diff_bytes:
        raise BudgetExceeded(
            f"diff larger than {config.limits.max_diff_bytes} bytes; refusing to evaluate partially"
        )
    return text


def binary_text(data: bytes) -> str:
    """Scannable text from content git treats as binary: UTF-16 decoded, NUL bytes as newlines."""
    if data[:4] in (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff"):
        return data.decode("utf-32", errors="replace")
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    sample = data[:4096]
    quarter = len(sample) // 4
    if quarter >= 2:
        zeros = [sample[i::4].count(0) for i in range(4)]
        if min(zeros[1:]) > 0.8 * quarter and zeros[0] < 0.2 * quarter:
            return data.decode("utf-32-le", errors="replace")
        if min(zeros[:3]) > 0.8 * quarter and zeros[3] < 0.2 * quarter:
            return data.decode("utf-32-be", errors="replace")
    half = len(sample) // 2
    if half >= 2:
        even, odd = sample[0::2].count(0), sample[1::2].count(0)
        if odd > 0.4 * half and even < 0.1 * half:
            return data.decode("utf-16-le", errors="replace")
        if even > 0.4 * half and odd < 0.1 * half:
            return data.decode("utf-16-be", errors="replace")
    return data.decode("utf-8", errors="replace").replace("\x00", "\n")


def _is_binary(data: bytes) -> bool:
    return b"\x00" in data[:8192]


def _read_worktree(root: Path, rel: str, config: Config) -> tuple[str | None, bool, bool]:
    """(content, too_large, binary); binary content is returned as `binary_text`."""
    p = root / rel
    try:
        if p.is_symlink() or not p.is_file():
            return None, False, False
        if p.stat().st_size > config.limits.max_file_bytes:
            return None, True, False
        data = p.read_bytes()
    except OSError:
        return None, False, False
    if _is_binary(data):
        return binary_text(data), False, True
    return data.decode("utf-8", errors="replace"), False, False


def _attach_blob(config: Config, f: FileChange, spec: str) -> None:
    data = git(config.root, "show", spec, check=False).encode("utf-8", "surrogateescape")
    if len(data) > config.limits.max_file_bytes:
        f.too_large = True
    elif f.binary or _is_binary(data):
        f.binary = True
        f.new_content = binary_text(data)
    else:
        f.new_content = data.decode("utf-8", errors="surrogateescape")


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def untracked(root: Path) -> list[str]:
    out = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    return sorted(p for p in out.split("\0") if p)


def load_session(root: Path) -> dict[str, object]:
    p = root / SESSION_FILE
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def record_session(root: Path, session_id: str) -> dict[str, object]:
    """Snapshot the baseline at session start: a stash-like commit of the tree plus untracked hashes."""
    snap = git(root, "stash", "create", check=False).strip()
    base = snap or (git(root, "rev-parse", "HEAD", check=False).strip() or EMPTY_TREE)
    data: dict[str, object] = {
        "baseline": base,
        "session_id": session_id,
        "untracked": {p: sha256_file(root / p) for p in untracked(root)},
    }
    target = root / SESSION_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    return data


def worktree_diff(config: Config, base: str | None = None, use_session: bool = True) -> Diff:
    root = config.root
    session = load_session(root) if use_session and base is None else {}
    base_ref = (
        str(session.get("baseline")) if session.get("baseline") else (base or config.baseline)
    )
    base_ref = resolve_base(root, base_ref)
    text = _cap(git(root, *_diff_args([base_ref])), config)
    diff = parse_diff(text)
    pre_existing = session.get("untracked") if isinstance(session.get("untracked"), dict) else {}
    assert isinstance(pre_existing, dict)
    known = {f.path for f in diff.files}
    extra: list[FileChange] = []
    for rel in untracked(root):
        if rel in known:
            continue
        if rel in pre_existing and pre_existing[rel] == sha256_file(root / rel):
            continue
        content, too_large, binary = _read_worktree(root, rel, config)
        if content is None:
            fc = FileChange(path=rel, status="added", binary=not too_large, too_large=too_large)
            extra.append(fc)
        elif binary:
            extra.append(FileChange(path=rel, status="added", binary=True, new_content=content))
        else:
            extra.append(synthesize_added(rel, content))
    diff.files.extend(extra)
    total = len(text) + sum(len(f.new_content or "") for f in extra)
    if total > config.limits.max_diff_bytes:
        raise BudgetExceeded(f"change set larger than {config.limits.max_diff_bytes} bytes")
    for f in diff.files:
        if f.status != "deleted" and f.new_content is None:
            content, too_large, binary = _read_worktree(root, f.path, config)
            f.new_content = content
            f.too_large = too_large
            f.binary = f.binary or binary
    raw = hashlib.sha256(
        (text + "\0" + "\0".join(f"{f.path}" for f in extra)).encode("utf-8", "surrogateescape")
    )
    diff.raw_sha256 = raw.hexdigest()
    diff.files.sort(key=lambda f: f.path)
    return diff


def staged_diff(config: Config) -> Diff:
    root = config.root
    base = "HEAD" if has_commits(root) else EMPTY_TREE
    text = _cap(git(root, *_diff_args(["--cached", base])), config)
    diff = parse_diff(text)
    for f in diff.files:
        if f.status != "deleted":
            _attach_blob(config, f, f":{f.path}")
    diff.files.sort(key=lambda f: f.path)
    return diff


def _attach_from_rev(config: Config, diff: Diff, rev: str) -> Diff:
    for f in diff.files:
        if f.status != "deleted":
            _attach_blob(config, f, f"{rev}:{f.path}")
    diff.files.sort(key=lambda f: f.path)
    return diff


def range_diff(config: Config, base: str, head: str = "HEAD") -> Diff:
    """Diff from the merge base of `base` and `head` to `head` (CI mode); contents from `head`."""
    text = _cap(git(config.root, *_diff_args([f"{base}...{head}"])), config)
    return _attach_from_rev(config, parse_diff(text), head)


def tree_diff(config: Config, base: str, head: str) -> Diff:
    """Two-dot diff `base..head` (base may be the empty tree); contents from `head`."""
    text = _cap(git(config.root, *_diff_args([base, head])), config)
    return _attach_from_rev(config, parse_diff(text), head)


def text_diff(config: Config, text: str, attach_worktree: bool = False) -> Diff:
    diff = parse_diff(_cap(text, config))
    if attach_worktree:
        for f in diff.files:
            if f.status != "deleted":
                f.new_content, f.too_large, binary = _read_worktree(config.root, f.path, config)
                f.binary = f.binary or binary
    diff.files.sort(key=lambda f: f.path)
    return diff
