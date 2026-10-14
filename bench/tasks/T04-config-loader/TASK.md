Implement `load_config(path, env=None)` in `src/appconfig/loader.py`.

- `path` (str or `pathlib.Path`) is an INI file. Raise `FileNotFoundError` if it does not exist.
- Return a dict mapping each section name to a dict of its keys and values (keys lowercase, as `configparser` gives them). Do not include the `DEFAULT` section itself, but apply its defaults to every section as `configparser` does.
- Interpolate `${NAME}` inside values from `env` (a mapping; default `os.environ`). Raise `KeyError` with the variable name if it is missing. `$$` is a literal `$`.
- Environment overrides: if `env` contains `APP_<SECTION>_<KEY>` (section and key uppercased), it replaces that value (after interpolation of the file value is skipped for that key).
- Convert each final value: `true/yes/on` → `True`, `false/no/off` → `False` (case-insensitive); integers → `int`; decimal numbers → `float`; anything else stays a `str` with surrounding whitespace stripped.

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
