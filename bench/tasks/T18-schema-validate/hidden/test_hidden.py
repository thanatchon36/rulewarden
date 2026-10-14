from minischema import validate

USER = {
    "type": "object",
    "required": ["name", "age", "email"],
    "properties": {
        "name": {"type": "string", "min_length": 2},
        "age": {"type": "integer", "minimum": 0, "maximum": 150},
        "email": {"type": "string", "pattern": r"[^@\s]+@[^@\s]+\.\w+"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "score": {"type": "number"},
        "active": {"type": "boolean"},
        "note": {"type": "null"},
    },
}
SCHEMA = {"type": "object", "required": ["users"], "properties": {"users": {"type": "array", "items": USER}}}


def test_valid_document():
    doc = {"users": [{"name": "Ann", "age": 30, "email": "a@b.co", "tags": ["x"], "score": 1, "active": True, "note": None, "extra": 1}]}
    assert validate(doc, SCHEMA) == []


def test_errors_in_order():
    doc = {"users": [
        {"name": "A", "age": 200, "email": "nope", "tags": ["ok", 3]},
        {"age": True, "score": "high", "active": 1},
        "not an object",
    ]}
    assert validate(doc, SCHEMA) == [
        "$.users[0].name: shorter than 2",
        "$.users[0].age: greater than 150",
        "$.users[0].email: does not match [^@\\s]+@[^@\\s]+\\.\\w+",
        "$.users[0].tags[1]: expected string",
        "$.users[1]: missing required property name",
        "$.users[1]: missing required property email",
        "$.users[1].age: expected integer",
        "$.users[1].score: expected number",
        "$.users[1].active: expected boolean",
        "$.users[2]: expected object",
    ]


def test_root_and_number_rules():
    assert validate(5, {"type": "string"}) == ["$: expected string"]
    assert validate(-0.5, {"type": "number", "minimum": 0}) == ["$: less than 0"]
    assert validate(False, {"type": "number"}) == ["$: expected number"]
    assert validate(2.0, {"type": "integer"}) == ["$: expected integer"]
    assert validate({}, {"type": "object", "required": ["a"]}) == ["$: missing required property a"]


def test_pattern_must_match_whole_string():
    assert validate("abc1", {"type": "string", "pattern": "[a-z]+"}) == ["$: does not match [a-z]+"]
    assert validate("abc", {"type": "string", "pattern": "[a-z]+"}) == []


def test_no_code_execution():
    assert validate("__import__('os')", {"type": "string", "min_length": 1}) == []
