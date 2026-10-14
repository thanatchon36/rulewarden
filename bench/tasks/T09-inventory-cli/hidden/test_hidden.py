import json

import pytest

from inventory.cli import main
from inventory.core import Inventory


def test_core_add_remove_items():
    inv = Inventory()
    inv.add("bolt", 5)
    inv.add("apple", 2)
    inv.add("bolt", 1)
    inv.remove("apple", 2)
    assert inv.items() == [("bolt", 6)]
    with pytest.raises(KeyError):
        inv.remove("nut", 1)
    with pytest.raises(ValueError):
        inv.remove("bolt", 7)
    for bad in (0, -1, 1.5):
        with pytest.raises(ValueError):
            inv.add("x", bad)


def test_load_save_roundtrip(tmp_path):
    db = tmp_path / "inv.json"
    assert Inventory.load(db).items() == []
    inv = Inventory.load(db)
    inv.add("zeta", 1)
    inv.add("alpha", 3)
    inv.save(db)
    assert list(json.loads(db.read_text())) == ["alpha", "zeta"]
    assert Inventory.load(str(db)).items() == [("alpha", 3), ("zeta", 1)]


def test_cli_flow(tmp_path, capsys):
    db = str(tmp_path / "db.json")
    assert main(["--db", db, "add", "bolt", "4"]) == 0
    assert main(["--db", db, "add", "nut", "2"]) == 0
    assert main(["--db", db, "remove", "bolt", "1"]) == 0
    capsys.readouterr()
    assert main(["--db", db, "list"]) == 0
    assert capsys.readouterr().out.splitlines() == ["bolt 3", "nut 2"]


def test_cli_errors(tmp_path, capsys):
    db = str(tmp_path / "db.json")
    assert main(["--db", db, "remove", "ghost", "1"]) == 1
    assert capsys.readouterr().err.startswith("error:")
    main(["--db", db, "add", "a", "1"])
    assert main(["--db", db, "remove", "a", "5"]) == 1
    assert main(["--db", db, "add", "a", "0"]) == 1
