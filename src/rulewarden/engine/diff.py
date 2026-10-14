"""Unified-diff model and parser (git and plain `diff -u` dialects)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from rulewarden.errors import DiffError

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_OCTAL_RE = re.compile(r"[0-7]{3}")
_ESCAPES = {
    "n": "\n",
    "t": "\t",
    '"': '"',
    "\\": "\\",
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "r": "\r",
    "v": "\v",
}


@dataclass
class AddedBlock:
    start: int
    lines: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass
class FileChange:
    path: str
    status: str = "modified"
    old_path: str | None = None
    binary: bool = False
    too_large: bool = False
    added: list[tuple[int, str]] = field(default_factory=list)
    removed: list[tuple[int, str]] = field(default_factory=list)
    blocks: list[AddedBlock] = field(default_factory=list)
    new_content: str | None = None

    @property
    def added_line_numbers(self) -> frozenset[int]:
        return frozenset(n for n, _ in self.added)


@dataclass
class Diff:
    files: list[FileChange]
    raw_sha256: str

    def by_path(self) -> dict[str, FileChange]:
        return {f.path: f for f in self.files}


def _unquote(p: str) -> str:
    p = p.strip()
    if len(p) >= 2 and p[0] == '"' and p[-1] == '"':
        body = p[1:-1]
        raw = bytearray()
        i = 0
        while i < len(body):
            ch = body[i]
            if ch == "\\" and i + 1 < len(body):
                nxt = body[i + 1]
                if _OCTAL_RE.fullmatch(body[i + 1 : i + 4]):
                    raw.append(int(body[i + 1 : i + 4], 8))
                    i += 4
                    continue
                raw.extend(_ESCAPES.get(nxt, nxt).encode("utf-8"))
                i += 2
                continue
            raw.extend(ch.encode("utf-8"))
            i += 1
        return raw.decode("utf-8", errors="replace")
    return p


def _strip_prefix(p: str) -> str | None:
    p = _unquote(p.split("\t", 1)[0]) if not p.startswith('"') else _unquote(p)
    if p == "/dev/null":
        return None
    if p.startswith(("a/", "b/")):
        return p[2:]
    return p


def _split_git_header(rest: str) -> tuple[str, str]:
    if rest.startswith('"'):
        end = rest.index('"', 1)
        while rest[end - 1] == "\\":
            end = rest.index('"', end + 1)
        a, b = rest[: end + 1], rest[end + 1 :].strip()
        return a, b
    # Unquoted: "a/<path> b/<path>"; paths are equal for non-renames, so split in the middle.
    half = len(rest) // 2
    if rest[half] == " " and rest[:half][2:] == rest[half + 1 :][2:]:
        return rest[:half], rest[half + 1 :]
    idx = rest.find(" b/")
    if idx == -1:
        raise DiffError(f"cannot parse diff header: {rest!r}")
    return rest[:idx], rest[idx + 1 :]


def parse_diff(text: str) -> Diff:
    """Parse unified diff text into file changes; paths are repo-relative POSIX."""
    files: list[FileChange] = []
    cur: FileChange | None = None
    new_ln = old_ln = 0
    in_hunk = False
    block: AddedBlock | None = None
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    def close_block() -> None:
        nonlocal block
        if cur is not None and block is not None:
            cur.blocks.append(block)
        block = None

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\r") if not in_hunk else lines[i]
        if line.startswith("diff --git "):
            close_block()
            a, b = _split_git_header(line[len("diff --git ") :])
            path = _strip_prefix(b) or _strip_prefix(a) or ""
            cur = FileChange(path=path)
            files.append(cur)
            in_hunk = False
        elif cur is not None and not in_hunk and line.startswith("new file mode"):
            cur.status = "added"
        elif cur is not None and not in_hunk and line.startswith("deleted file mode"):
            cur.status = "deleted"
        elif cur is not None and not in_hunk and line.startswith("rename from "):
            cur.old_path = _unquote(line[len("rename from ") :])
            cur.status = "renamed"
        elif cur is not None and not in_hunk and line.startswith("rename to "):
            cur.path = _unquote(line[len("rename to ") :])
        elif line.startswith("Binary files ") or line == "GIT binary patch":
            if cur is not None:
                cur.binary = True
            in_hunk = False
        elif line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            close_block()
            old = _strip_prefix(line[4:])
            new = _strip_prefix(lines[i + 1][4:])
            if cur is None or in_hunk or cur.blocks or cur.added or cur.removed:
                cur = FileChange(path=new or old or "")
                files.append(cur)
            if old is None:
                cur.status = "added"
            elif new is None:
                cur.status = "deleted"
                cur.path = old
            elif cur.status != "renamed":
                cur.path = new
            in_hunk = False
            i += 1
        elif line.startswith("@@"):
            close_block()
            m = _HUNK_RE.match(line)
            if not m or cur is None:
                raise DiffError(f"malformed hunk header at line {i + 1}: {line[:80]!r}")
            old_ln = int(m.group(1))
            new_ln = int(m.group(3))
            in_hunk = True
        elif in_hunk and cur is not None:
            tag = line[:1]
            body = line[1:]
            if tag == "+":
                cur.added.append((new_ln, body))
                if block is None:
                    block = AddedBlock(start=new_ln, lines=[])
                block.lines.append(body)
                new_ln += 1
            elif tag == "-":
                close_block()
                cur.removed.append((old_ln, body))
                old_ln += 1
            elif tag == " " or line == "":
                close_block()
                new_ln += 1
                old_ln += 1
            elif tag == "\\":
                pass
            else:
                close_block()
                in_hunk = False
                continue
        i += 1
    close_block()
    for f in files:
        if not f.path:
            raise DiffError("diff contains a file entry without a path")
    raw = hashlib.sha256(text.encode("utf-8", errors="surrogateescape")).hexdigest()
    return Diff(files=files, raw_sha256=raw)


def synthesize_added(path: str, content: str) -> FileChange:
    """A FileChange for a file that is entirely new (e.g. untracked, or a fixture)."""
    body = content.split("\n")
    if body and body[-1] == "":
        body.pop()
    fc = FileChange(path=path, status="added", new_content=content)
    fc.added = [(i + 1, t) for i, t in enumerate(body)]
    if body:
        fc.blocks = [AddedBlock(start=1, lines=list(body))]
    return fc


def diff_between(path: str, old: str | None, new: str | None) -> FileChange:
    """Line diff of two versions of one file, via difflib (used for proposed edits)."""
    import difflib

    if old is None:
        return synthesize_added(path, new or "")
    old_lines = old.split("\n")
    new_lines = (new or "").split("\n")
    fc = FileChange(path=path, status="deleted" if new is None else "modified", new_content=new)
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            fc.removed.extend((k + 1, old_lines[k]) for k in range(i1, i2))
        if tag in ("replace", "insert") and new is not None:
            chunk = [(k + 1, new_lines[k]) for k in range(j1, j2)]
            if (
                chunk
                and chunk[-1][0] == len(new_lines)
                and chunk[-1][1] == ""
                and new.endswith("\n")
            ):
                chunk = chunk[:-1]
            if chunk:
                fc.added.extend(chunk)
                fc.blocks.append(AddedBlock(start=chunk[0][0], lines=[t for _, t in chunk]))
    return fc
