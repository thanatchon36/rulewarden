Implement `toc(markdown, max_level=3) -> str` in `src/mdtoc/toc.py`, producing a table of contents for ATX headings (`#` to `######` followed by a space).

- Ignore headings inside fenced code blocks (lines starting with ```` ``` ```` or `~~~` open and close a fence).
- Skip headings deeper than `max_level`.
- Title: the heading text with surrounding whitespace and any closing `#` sequence removed (`## Setup ##` → `Setup`).
- Anchor (GitHub style): lowercase the title, remove every character that is not a letter, digit, space, hyphen or underscore, then replace each space with `-`. If an anchor was already used, append `-1`, `-2`, … (the first duplicate gets `-1`).
- Output one line per heading: `<indent>- [Title](#anchor)`, where indent is two spaces per level below the shallowest included heading level. Lines end with `\n`; no headings → empty string.

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
