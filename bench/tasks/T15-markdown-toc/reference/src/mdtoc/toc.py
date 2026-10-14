import re

_HEADING = re.compile(r"^(#{1,6}) +(.*?)(?: +#+)?\s*$")
_FENCE = re.compile(r"^(```|~~~)")
_DROP = re.compile(r"[^\w\- ]", re.UNICODE)


def _anchor(title: str, used: dict[str, int]) -> str:
    base = _DROP.sub("", title.lower()).replace(" ", "-")
    n = used.get(base, 0)
    used[base] = n + 1
    return base if n == 0 else f"{base}-{n}"


def toc(markdown: str, max_level: int = 3) -> str:
    """Nested Markdown bullet list linking to the document's ATX headings."""
    in_fence = False
    found: list[tuple[int, str]] = []
    for line in markdown.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        m = None if in_fence else _HEADING.match(line)
        if m and len(m.group(1)) <= max_level:
            found.append((len(m.group(1)), m.group(2).strip()))
    if not found:
        return ""
    top = min(level for level, _ in found)
    used: dict[str, int] = {}
    return "".join(f"{'  ' * (lvl - top)}- [{t}](#{_anchor(t, used)})\n" for lvl, t in found)
