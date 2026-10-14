import re

_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _scalar(data: object, schema: dict, path: str) -> list[str]:
    errors = []
    if isinstance(data, str):
        if len(data) < schema.get("min_length", 0):
            errors.append(f"{path}: shorter than {schema['min_length']}")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], data):
            errors.append(f"{path}: does not match {schema['pattern']}")
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(f"{path}: less than {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            errors.append(f"{path}: greater than {schema['maximum']}")
    return errors


def validate(data: object, schema: dict, path: str = "$") -> list[str]:
    """Validate `data` against a small schema; return messages in document order."""
    kind = schema.get("type")
    if kind and not _CHECKS[kind](data):
        return [f"{path}: expected {kind}"]
    if isinstance(data, dict):
        errors = [f"{path}: missing required property {n}" for n in schema.get("required", []) if n not in data]
        for name, sub in schema.get("properties", {}).items():
            if name in data:
                errors += validate(data[name], sub, f"{path}.{name}")
        return errors
    if isinstance(data, list):
        items = schema.get("items")
        return [e for i, v in enumerate(data) for e in (validate(v, items, f"{path}[{i}]") if items else [])]
    return _scalar(data, schema, path)
