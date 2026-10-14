"""Generate docs/pages/cli.md and docs/pages/rules.md from the code, so the reference cannot drift.

The CLI page is the `--help` text of every command; the rule catalogue is read from the shipped
packs in src/rulewarden/packs/. tests/test_docs_generated.py fails if either file is stale.
Usage: uv run --frozen python docs/gen_reference.py
"""

from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path

import yaml
from click.testing import CliRunner

from rulewarden.cli import main as cli

PAGES = Path(__file__).resolve().parent / "pages"
SEVERITY_ORDER = {"critical": 0, "required": 1, "advisory": 2}


def cli_page() -> str:
    runner = CliRunner()
    out = [
        "# CLI reference",
        "",
        "Generated from `rulewarden <command> --help` by `docs/gen_reference.py`.",
        "",
        "Exit codes: `0` pass or advisory findings only · `1` blocking findings · `3` engine or configuration error.",
        "",
    ]
    top = runner.invoke(cli, ["--help"], prog_name="rulewarden", terminal_width=100)
    out += ["## rulewarden", "", "```text", top.output.rstrip(), "```", ""]
    for name in sorted(cli.commands):  # type: ignore[attr-defined]
        res = runner.invoke(cli, [name, "--help"], prog_name="rulewarden", terminal_width=100)
        out += [f"## rulewarden {name}", "", "```text", res.output.rstrip(), "```", ""]
    return "\n".join(out)


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def rules_page() -> str:
    packs = sorted(
        p for p in resources.files("rulewarden.packs").iterdir() if p.name.endswith(".yaml")
    )
    total = 0
    sections: list[str] = []
    for pack in packs:
        data = yaml.safe_load(pack.read_text(encoding="utf-8"))
        rules = data.get("rules", [])
        total += len(rules)
        desc = " ".join(str(data.get("description", "")).split())
        sections += [f"## `{data.get('pack', pack.name[:-5])}`", ""]
        if desc:
            sections += [desc, ""]
        sections += ["| ID | Rule | Severity | Tier | Engine | Fix |", "|---|---|---|---|---|---|"]
        for r in sorted(rules, key=lambda r: (SEVERITY_ORDER.get(r["severity"], 9), r["id"])):
            engine = (r.get("check") or {}).get("engine", "—")
            sections.append(
                f"| `{r['id']}` | {_cell(r['title'])} | {r['severity']} | {r['decidability']} | {engine} |"
                f" {_cell(r['message'])} |"
            )
        sections.append("")
    head = [
        "# Rule catalogue",
        "",
        f"The {len(packs)} starter packs ship {total} rules. Generated from `src/rulewarden/packs/` by",
        "`docs/gen_reference.py`. Every rule has at least one failing and one passing fixture;",
        "`rulewarden test-rules --path <pack dir>` runs them. Only `deterministic` rules with severity",
        "`required` or `critical` block; `heuristic` rules warn; `advisory` findings never block.",
        "",
    ]
    return "\n".join(head + sections)


def main() -> int:
    PAGES.mkdir(exist_ok=True)
    (PAGES / "cli.md").write_text(cli_page() + "\n", encoding="utf-8")
    (PAGES / "rules.md").write_text(rules_page() + "\n", encoding="utf-8")
    sys.stdout.write("wrote docs/pages/cli.md and docs/pages/rules.md\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
