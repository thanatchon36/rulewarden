from textkit import slugify


def test_truncation():
    assert slugify("the quick brown fox", max_length=12) == "the-quick"
