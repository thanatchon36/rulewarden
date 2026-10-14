import argparse
import sys

from inventory.core import Inventory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="inventory")
    parser.add_argument("--db", required=True)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("add", "remove"):
        p = sub.add_parser(name)
        p.add_argument("name")
        p.add_argument("qty", type=int)
    sub.add_parser("list")
    args = parser.parse_args(argv)
    inv = Inventory.load(args.db)
    try:
        if args.cmd == "add":
            inv.add(args.name, args.qty)
        elif args.cmd == "remove":
            inv.remove(args.name, args.qty)
        else:
            for name, qty in inv.items():
                print(f"{name} {qty}")
            return 0
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    inv.save(args.db)
    return 0
