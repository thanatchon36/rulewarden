"""Deterministic extraction of comment text by file type, used by `within: comments`."""

from __future__ import annotations

HASH_EXT = (
    ".py",
    ".sh",
    ".bash",
    ".zsh",
    ".rb",
    ".pl",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".ini",
    ".r",
    ".mk",
)
SLASH_EXT = (
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
    ".java",
    ".kt",
    ".rs",
    ".swift",
    ".cs",
)
DASH_EXT = (".sql", ".lua", ".hs")
PROSE_EXT = (".md", ".markdown", ".rst", ".txt")
PROSE_NAMES = (":commit-msg", "COMMIT_EDITMSG")


def style_for(path: str) -> str:
    low = path.lower()
    base = low.rsplit("/", 1)[-1]
    if base in (n.lower() for n in PROSE_NAMES) or low.endswith(PROSE_EXT):
        return "prose"
    if base in ("makefile", "dockerfile") or low.endswith(HASH_EXT):
        return "hash"
    if low.endswith(SLASH_EXT):
        return "slash"
    if low.endswith(DASH_EXT):
        return "dash"
    return "unknown"


def _outside_quotes_index(line: str, marker: str) -> int:
    quote: str | None = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ("'", '"', "`"):
            quote = ch
        elif line.startswith(marker, i):
            return i
        i += 1
    return -1


def comment_text(path: str, line: str) -> str | None:
    """The comment part of one source line, or None if the line has no comment.

    Block comments are approximated per line: a line starting with '*' or '/*' in
    slash-style files counts as comment text. Prose files are all comment text.
    """
    style = style_for(path)
    if style == "prose":
        return line
    if style == "hash":
        idx = _outside_quotes_index(line, "#")
        if idx == -1:
            return None
        if path.lower().endswith((".sh", ".bash", ".zsh")) and line[idx:].startswith("#!"):
            return None
        return line[idx + 1 :]
    if style == "slash":
        stripped = line.lstrip()
        if stripped.startswith(("/*", "*")):
            return stripped.lstrip("/*").rstrip("*/")
        idx = _outside_quotes_index(line, "//")
        return None if idx == -1 else line[idx + 2 :]
    if style == "dash":
        idx = _outside_quotes_index(line, "--")
        return None if idx == -1 else line[idx + 2 :]
    return None
