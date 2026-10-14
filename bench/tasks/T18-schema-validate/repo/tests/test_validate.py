from minischema import validate


def test_valid_string():
    assert validate("x", {"type": "string"}) == []
