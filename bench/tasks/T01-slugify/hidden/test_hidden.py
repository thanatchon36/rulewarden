import pytest

from textkit import slugify


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hello, World!", "hello-world"),
        ("  --Already--slugged--  ", "already-slugged"),
        ("Crème brûlée", "creme-brulee"),
        ("Ångström", "angstrom"),
        ("Straße", "strasse"),
        ("Æsir og ørn", "aesir-og-orn"),
        ("Łódź", "lodz"),
        ("日本語 text", "text"),
        ("a&b|c", "a-b-c"),
        ("v2.0 release", "v2-0-release"),
        ("", ""),
        ("!!!", ""),
    ],
)
def test_slugify(text, expected):
    assert slugify(text) == expected


def test_separator():
    assert slugify("Hello World", separator="_") == "hello_world"
    assert slugify("a b c", separator="--") == "a--b--c"
    with pytest.raises(ValueError):
        slugify("x", separator="")


def test_max_length_word_boundary():
    assert slugify("the quick brown fox", max_length=12) == "the-quick"
    assert slugify("the quick brown fox", max_length=9) == "the-quick"
    assert slugify("the quick brown fox", max_length=19) == "the-quick-brown-fox"


def test_max_length_hard_cut_and_no_trailing_separator():
    assert slugify("supercalifragilistic", max_length=5) == "super"
    assert slugify("ab cd", max_length=3) == "ab"
    assert not slugify("abc def ghi", max_length=8).endswith("-")


def test_max_length_invalid():
    with pytest.raises(ValueError):
        slugify("x", max_length=0)
