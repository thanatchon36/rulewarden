"""Deterministic rubric labels for corpus/data/rules.csv -> corpus/data/labels_rubric.csv.

Category: first matching rule in CATEGORY_RULES, else "other". Decidability (P3, relative
to a diff/command checker): deterministic = a concrete token plus a prohibition, or plus a
prescription that is not an obligation to act; heuristic = an approximate-quality cue.
`compilable` = a shipped `rulewarden compile` template matches. Rubric: corpus/README.md.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from rulewarden.compile.compiler import match_templates
from rulewarden.compile.extract import RuleLine

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

TOOLS = (
    r"npm|pnpm|yarn|bun|npx|pipx?|uv|poetry|conda|cargo|gradle|maven|mvn|make|cmake|docker|"
    r"kubectl|terraform|eslint|prettier|ruff|black|isort|flake8|mypy|pyright|tsc|biome|jq|curl|"
    r"wget|brew|git|gh|node|deno|python3?|pytest|jest|vitest|rspec|composer|dotnet|go (?:mod|test|build|run)"
)
_R = re.IGNORECASE

CONCRETE = re.compile(
    r"`[^`]+`"
    r"|(?:^|\s)\.?[\w-]+/[\w./-]+"
    r"|(?:^|[\s(])\.(?:env|gitignore|github|claude|cursor)\b"
    r"|\b[\w-]+\.(?:py|ts|tsx|js|jsx|json|ya?ml|toml|md|sh|go|rs|java|rb|lock|env|css|html|sql)\b"
    rf"|\b(?:{TOOLS})\b"
    r"|\b\d+\s*(?:lines?|chars?|characters|columns|cols|words|spaces|items|params|parameters|levels|%)"
    r"|console\.log|\bprint\(|\bany\b type|type\s+`?any|\bTODO\b|\bFIXME\b|\bemojis?\b|semicolons?"
    r"|single quotes|double quotes|\btabs\b|trailing whitespace|camelCase|snake_case|PascalCase|"
    r"kebab-case|SCREAMING_SNAKE|conventional commits?|--no-verify|force[- ]push|rm -rf|\bsudo\b"
    r"|api[ _-]?keys?|\bsecrets?\b|credentials?|passwords?|\bmain branch\b|\bmaster\b",
    _R,
)
_LEAD = r"^\W*(?:(?:critical|important|note|rule|always|please)\b\W*)*"
PROHIBITION = re.compile(
    r"\b(?:never|do not|don['’]?t|dont|must not|mustn['’]?t|should not|shouldn['’]?t|forbidden|"
    r"avoid)\b|" + _LEAD + r"no\b",
    _R,
)
PRESCRIPTION = re.compile(
    r"\b(?:must|always|should|prefer|only|instead of|rather than|required|make sure|ensure|"
    r"at most|no more than)\b|" + _LEAD + r"(?:use|keep|limit|put|place|name|prefix|import|store|"
    r"format|indent|wrap|declare|mark|add|write|return|call|set|follow|match)\b",
    _R,
)
ACTION_OBLIGATION = re.compile(
    _LEAD + r"(?:run|execute|build|test|verify|check|lint|read|review|ask|confirm|plan|update|"
    r"document|look|search|explore|consult|open)\b",
    _R,
)
HEURISTIC = re.compile(
    r"\b(?:short|small|concise|minimal|brief|long|large|complex(?:ity)?|duplicat\w*|DRY|focused|"
    r"single responsibility|nest(?:ed|ing)|early returns?|magic numbers?|excessive|too many|"
    r"unnecessary|redundant|obvious|self-documenting|descriptive|meaningful names?|sparingly|"
    r"verbose|succinct|terse|tiny|bloat\w*|over-?engineer\w*|dead code|unused)\b",
    _R,
)

CATEGORY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "security",
        re.compile(
            r"secret|credential|api[ _-]?key|\btokens?\b|password|\.env\b|private key|\bauth\w*|"
            r"vulnerab|injection|sanitiz|\bxss\b|csrf|encrypt|security|\bunsafe\b|\beval\b|\bsudo\b|"
            r"chmod|\bPII\b|personal data",
            _R,
        ),
    ),
    (
        "testing",
        re.compile(
            r"\btests?\b|testing|\bspecs?\b|coverage|\btdd\b|assert|\bmocks?\b|fixtures?|pytest|"
            r"jest|vitest|\bunit\b|\be2e\b|playwright|cypress",
            _R,
        ),
    ),
    (
        "scope",
        re.compile(
            r"(?:never|do not|don['’]?t|dont|only|avoid|without)\b.{0,40}\b(?:modify|edit|touch|"
            r"change|delete|remove|create|add|rename|move|overwrite)\b.{0,50}\b(?:files?|director\w*|"
            r"folders?|paths?|outside|/|unrelated|existing|dependenc\w*|packages?|config\w*)"
            r"|out of scope|scope of|unrelated changes|new dependenc\w*",
            _R,
        ),
    ),
    (
        "process",
        re.compile(
            r"\bcommits?\b|pull requests?|\bPRs?\b|\bbranch\w*|\bmerge\b|rebase|\bpush\b|review|"
            r"changelog|\bissues?\b|ticket|deploy|release|ask (?:the user|me|for|before)|confirm|"
            r"\bplan\b|planning|todo list|before (?:starting|making|committing|you)|after (?:each|every|"
            r"making|completing)|workflow|\bstep\b|document(?:ation)?\b|\bREADME\b",
            _R,
        ),
    ),
    (
        "tooling",
        re.compile(
            rf"\b(?:{TOOLS})\b|package manager|\binstall\b|\bscripts?\b|\bcommands?\b|\bcli\b|"
            r"\bbuild\b|\blint\w*|\bformatter\b",
            _R,
        ),
    ),
    (
        "voice",
        re.compile(
            r"\bcomments?\b|docstrings?|\bemojis?\b|\btone\b|respond|\brepl(?:y|ies)\b|\banswers?\b|"
            r"language|english|concise|verbose|\bexplain|wording|phrases?|apolog|tell the user|"
            r"communicat|\bprose\b|\bwrite in\b",
            _R,
        ),
    ),
    (
        "style",
        re.compile(
            r"\bnam(?:e|es|ing)\b|camel|snake|pascal|kebab|indent|format\w*|type hints?|typing|"
            r"\btypes?\b|\bimports?\b|functions?|\bclass(?:es)?\b|variables?|\bconst\b|\blet\b|"
            r"\bvar\b|async|await|line length|semicolon|quotes|\bstyle\b|patterns?|idiom|readab|"
            r"\bclean\b|simpl\w*|\bDRY\b|duplicat|components?|hooks?\b|interfaces?|error handling|"
            r"exceptions?|logging",
            _R,
        ),
    ),
)

FIELDS = ("rule_id", "category", "decidability", "compilable", "template")


def category(text: str) -> str:
    for name, pat in CATEGORY_RULES:
        if pat.search(text):
            return name
    return "other"


def decidability(text: str) -> str:
    concrete = bool(CONCRETE.search(text))
    if concrete and PROHIBITION.search(text):
        return "deterministic"
    if ACTION_OBLIGATION.search(text):
        return "undecidable"
    if concrete and PRESCRIPTION.search(text):
        return "deterministic"
    if HEURISTIC.search(text):
        return "heuristic"
    return "undecidable"


def label(text: str) -> dict[str, str]:
    template, _ = match_templates(RuleLine(0, text))
    return {
        "category": category(text),
        "decidability": decidability(text),
        "compilable": "1" if template else "0",
        "template": template,
    }


def main() -> int:
    with (DATA / "rules.csv").open(encoding="utf-8", newline="") as fh:
        rules = list(csv.DictReader(fh))
    out = []
    for r in rules:
        if r["redacted"] == "1":
            out.append(
                {
                    "rule_id": r["rule_id"],
                    "category": "security",
                    "decidability": "deterministic",
                    "compilable": "0",
                    "template": "",
                }
            )
            continue
        out.append({"rule_id": r["rule_id"], **label(r["text"])})
    with (DATA / "labels_rubric.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print(f"labelled {len(out)} lines", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
