import json
from pathlib import Path


def _check(qty: object) -> int:
    if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1:
        raise ValueError(f"quantity must be a positive integer, got {qty!r}")
    return qty


class Inventory:
    """Item quantities with JSON persistence."""

    def __init__(self, stock: dict[str, int] | None = None) -> None:
        self._stock = dict(stock or {})

    @classmethod
    def load(cls, path: str | Path) -> "Inventory":
        p = Path(path)
        return cls(json.loads(p.read_text(encoding="utf-8")) if p.exists() else {})

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self._stock, sort_keys=True), encoding="utf-8")

    def add(self, name: str, qty: int) -> None:
        self._stock[name] = self._stock.get(name, 0) + _check(qty)

    def remove(self, name: str, qty: int) -> None:
        _check(qty)
        if name not in self._stock:
            raise KeyError(name)
        if qty > self._stock[name]:
            raise ValueError(f"only {self._stock[name]} {name} in stock")
        self._stock[name] -= qty
        if self._stock[name] == 0:
            del self._stock[name]

    def items(self) -> list[tuple[str, int]]:
        return sorted(self._stock.items())
