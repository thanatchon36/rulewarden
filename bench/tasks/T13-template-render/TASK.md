Implement `scripts/render.sh TEMPLATE VALUES`. `TEMPLATE` is a text file with placeholders `{{name}}` or dotted paths `{{db.host}}` (letters, digits, `_` and `.`). `VALUES` is a JSON object.

- Print the template to stdout with every placeholder replaced by the value at that path. Strings are inserted literally (characters such as `/`, `&`, `\` and newlines must survive unchanged); numbers and booleans are inserted as JSON text (`5432`, `true`).
- If any placeholder's path is missing or `null`, or the value is an object or array, print `render.sh: bad key <path>` to stderr for each such path (in order of first appearance, once each), print nothing to stdout, and exit 1.
- Wrong number of arguments: usage message on stderr, exit 2. Missing files or invalid JSON: message on stderr, exit 1.
- The output must end exactly as the template ends (keep or omit the final newline as in the template).

Add tests for the new behaviour in a new test file (pytest is used to run the script). Run the test suite with `python -m pytest -q`.
