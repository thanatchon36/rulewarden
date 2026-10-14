"""Build human.patch (NEEDS_HUMAN H5, H6, H7) from the current repository files.

Reads the protected files and writes only proposals/h5-h7/human.patch. A human reviews the
patch, applies it with `git apply`, and locks; the agent never edits the protected files.
"""

import difflib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "human.patch"
PINNED = str(Path.home() / ".local" / "bin" / "rulewarden")


def main() -> int:
    changes: dict[str, tuple[str | None, str]] = {}

    # H6: anchor PRT-002's rules/ alternative so nested directories named rules/ do not match.
    p = REPO.joinpath("rules", "packs", "protected-set.yaml")
    old = p.read_text()
    needle = r"[^;&|\n]*(\brules/|"
    assert old.count(needle) == 1, "PRT-002 pattern not found exactly once"
    new = old.replace(needle, r"[^;&|\n]*((?<![\w./-])(\./)?rules/|")
    anchor = '        - "echo done > build/out.txt"\n'
    assert new.count(anchor) == 1, "PRT-002 pass fixture anchor not found"
    new = new.replace(anchor, anchor + '        - "cp a.yaml bench/rules/x.yaml"\n')
    changes["rules/packs/protected-set.yaml"] = (old, new)

    # H5: allow a .pre-commit-hooks.yaml consumer manifest at the repository root.
    p = REPO.joinpath("rules", "packs", "scope.yaml")
    old = p.read_text()
    needle = '".pre-commit-config.yaml"]'
    assert old.count(needle) == 1, "SCP-001 path list end not found"
    changes["rules/packs/scope.yaml"] = (
        old,
        old.replace(needle, '".pre-commit-config.yaml", ".pre-commit-hooks.yaml"]'),
    )
    changes[".pre-commit-hooks.yaml"] = (
        None,
        (Path(__file__).parent / "pre-commit-hooks.yaml").read_text(),
    )

    # H7: run the Claude Code hooks from a pinned, separately installed binary.
    p = REPO.joinpath(".claude", "settings.json")
    old = p.read_text()
    data = json.loads(old)
    count = 0
    for groups in data["hooks"].values():
        for g in groups:
            for h in g["hooks"]:
                if h.get("command") == "${CLAUDE_PROJECT_DIR}/.venv/bin/rulewarden":
                    h["command"] = PINNED
                    count += 1
    assert count == 4, f"expected 4 hook commands, found {count}"
    changes[".claude/settings.json"] = (old, json.dumps(data, indent=2) + "\n")

    out = []
    for path, (before, after) in changes.items():
        a = [] if before is None else before.splitlines(keepends=True)
        b = after.splitlines(keepends=True)
        if before is None:
            out.append(f"diff --git a/{path} b/{path}\nnew file mode 100644\n")
            out.extend(difflib.unified_diff(a, b, "/dev/null", f"b/{path}"))
        else:
            out.append(f"diff --git a/{path} b/{path}\n")
            out.extend(difflib.unified_diff(a, b, f"a/{path}", f"b/{path}"))
    OUT.write_text("".join(out))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
