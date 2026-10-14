import pytest

from ttlcache import TTLCache


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_expiry_and_default():
    clk = Clock()
    c = TTLCache(3, 5, clock=clk)
    c.set("a", 1)
    clk.t = 4.9
    assert c.get("a") == 1 and "a" in c and len(c) == 1
    clk.t = 5.0
    assert c.get("a", "gone") == "gone" and "a" not in c and len(c) == 0


def test_lru_eviction_and_recency():
    clk = Clock()
    c = TTLCache(2, 100, clock=clk)
    c.set("a", 1)
    c.set("b", 2)
    assert c.get("a") == 1
    c.set("c", 3)
    assert "b" not in c and c.get("a") == 1 and c.get("c") == 3


def test_replace_refreshes_and_resets_ttl():
    clk = Clock()
    c = TTLCache(2, 10, clock=clk)
    c.set("a", 1)
    c.set("b", 2)
    clk.t = 8
    c.set("a", 10)
    c.set("c", 3)
    assert "b" not in c
    clk.t = 15
    assert c.get("a") == 10


def test_expired_entries_free_space_before_eviction():
    clk = Clock()
    c = TTLCache(2, 10, clock=clk)
    c.set("old", 0)
    clk.t = 5
    c.set("fresh", 1)
    clk.t = 11
    c.set("new", 2)
    assert c.get("fresh") == 1 and c.get("new") == 2 and len(c) == 2


def test_delete():
    clk = Clock()
    c = TTLCache(2, 1, clock=clk)
    c.set("a", 1)
    c.delete("a")
    with pytest.raises(KeyError):
        c.delete("a")
    c.set("b", 1)
    clk.t = 2
    with pytest.raises(KeyError):
        c.delete("b")


def test_validation_and_none_values():
    for args in [(0, 1), (1, 0), (-1, 5)]:
        with pytest.raises(ValueError):
            TTLCache(*args)
    c = TTLCache(1, 1, clock=Clock())
    c.set("n", None)
    assert "n" in c and c.get("n", "default") is None
