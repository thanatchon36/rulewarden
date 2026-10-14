import random

import pytest

from durations import format_duration, parse_duration


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("90s", 90),
        ("1d2h", 93600),
        ("2h 15m", 8100),
        ("1D 1S", 86401),
        ("  3m  ", 180),
        ("0s", 0),
        ("05:07", 307),
        ("1:00:00", 3600),
        ("123:59:59", 123 * 3600 + 3599),
        ("1d 2h 3m 4s", 93784),
    ],
)
def test_parse(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize("bad", ["", "  ", "5x", "1m2h", "1h1h", "-5s", "1.5h", "10", "5:60", "1:2:3", "h", "1h:2m"])
def test_parse_invalid(bad):
    with pytest.raises(ValueError):
        parse_duration(bad)


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0, "0s"), (59, "59s"), (60, "1m"), (3601, "1h 1s"), (93784, "1d 2h 3m 4s"), (172800, "2d")],
)
def test_format(seconds, text):
    assert format_duration(seconds) == text


def test_format_invalid():
    for bad in (-1, 1.5, "3"):
        with pytest.raises(ValueError):
            format_duration(bad)


def test_roundtrip():
    rng = random.Random(11)
    for _ in range(200):
        n = rng.randint(0, 10**7)
        assert parse_duration(format_duration(n)) == n
