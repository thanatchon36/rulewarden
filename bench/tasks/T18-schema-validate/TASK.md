Implement `validate(data, schema) -> list[str]` in `src/minischema/validate.py`. It returns a list of error messages (empty if valid), in document order.

Schema keywords:
- `type`: one of `object`, `array`, `string`, `integer`, `number`, `boolean`, `null`. `integer` accepts ints but not bools; `number` accepts ints and floats but not bools.
- For objects: `properties` (name → schema) and `required` (list of names). Unknown properties are allowed.
- For arrays: `items` (schema applied to every element).
- For strings: `min_length` and `pattern` (a regular expression that must match the whole string).
- For integers and numbers: `minimum` and `maximum` (inclusive).

Messages have the form `<path>: <problem>`, where the path starts at `$` and uses `.name` for properties and `[i]` for array items, for example `$.users[2].email: expected string`. Problems: `expected <type>`, `missing required property <name>`, `shorter than <n>`, `does not match <pattern>`, `less than <n>`, `greater than <n>`. When the type is wrong, report only the type error for that value. Report missing required properties (in the order listed in `required`) before errors inside the properties (in the order of `properties`).

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
