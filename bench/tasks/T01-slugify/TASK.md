Implement `slugify(text, max_length=None, separator="-")` in `src/textkit/slug.py`.

Behaviour:
1. Transliterate to ASCII: decompose accented letters and drop the accents (`é` → `e`, `Å` → `A`). Map `ß` → `ss`, `æ` → `ae`, `ø` → `o`, `ł` → `l`. Drop any other non-ASCII character.
2. Lowercase the result.
3. Replace every run of characters that are not `a-z` or `0-9` with a single `separator`.
4. Strip leading and trailing separators.
5. If `max_length` is given and the slug is longer, cut it to at most `max_length` characters. Cut at the last separator that keeps the result within the limit, if there is one; otherwise cut hard at `max_length`. The result never ends with a separator.
6. `separator` may be any non-empty string; raise `ValueError` if it is empty. Raise `ValueError` if `max_length` is given and is less than 1.

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
