Build a small inventory tool.

`src/inventory/core.py`: class `Inventory` holding item quantities.
- `Inventory.load(path)` (classmethod): read a JSON object `{name: quantity}` from `path`; a missing file means an empty inventory.
- `save(path)`: write the JSON object with keys sorted.
- `add(name, qty)`: `qty` must be a positive int, else `ValueError`.
- `remove(name, qty)`: `qty` must be a positive int; raise `KeyError` for an unknown item and `ValueError` if `qty` exceeds the stock. An item whose quantity reaches 0 is removed.
- `items()`: list of `(name, qty)` sorted by name.

`src/inventory/cli.py`: `main(argv=None) -> int` with argparse: `--db PATH` (required) and subcommands `add NAME QTY`, `remove NAME QTY`, `list`. `list` prints one `NAME QTY` line per item. On `KeyError`/`ValueError`, print `error: <message>` to stderr and return 1. Return 0 on success. Changes are saved to the database file.

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
