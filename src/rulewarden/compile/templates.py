"""Deterministic rule templates matched against instruction-file lines (§4.9, §4.10).

Each template is a regex over the lower-cased line plus a builder that returns rule bodies
(without id/source) carrying their own fixtures, so every proposal can be qualified (P6).
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

import yaml

RuleBody = dict[str, Any]
Builder = Callable[[re.Match[str], str], list[RuleBody]]


@lru_cache(maxsize=1)
def pack_rules() -> dict[str, RuleBody]:
    out: dict[str, RuleBody] = {}
    for entry in sorted(resources.files("rulewarden.packs").iterdir(), key=lambda e: e.name):
        if entry.name.endswith(".yaml"):
            data = yaml.safe_load(entry.read_text(encoding="utf-8"))
            for r in data["rules"]:
                check = r.get("check")
                if isinstance(check, dict) and True in check:  # YAML 1.1 reads `on` as true
                    r["check"] = {("on" if k is True else k): v for k, v in check.items()}
                r["pack_name"] = data.get("pack", entry.name.removesuffix(".yaml"))
                out[r["id"]] = r
    return out


def from_pack(*ids: str) -> Builder:
    def build(m: re.Match[str], line: str) -> list[RuleBody]:
        rules = []
        for rid in ids:
            body = copy.deepcopy(pack_rules()[rid])
            body.pop("id", None)
            body.pop("pack_name", None)
            body.setdefault("tags", []).append(f"from-pack:{rid}")
            rules.append(body)
        return rules

    return build


def _code_token(line: str) -> str | None:
    m = re.search(r"`([^`]{1,60})`", line)
    return m.group(1).strip() if m else None


def _forbid_token(m: re.Match[str], line: str) -> list[RuleBody]:
    token = _code_token(line)
    if not token:
        return []
    pat = re.escape(token)
    if re.match(r"\w", token):
        pat = r"\b" + pat
    if re.search(r"\w$", token):
        pat += r"\b"
    return [
        {
            "title": f"Do not use {token}",
            "severity": "required",
            "decidability": "deterministic",
            "applies_to": [
                "**/*.py",
                "**/*.sh",
                "**/*.js",
                "**/*.ts",
                "**/*.go",
                "**/*.rs",
                "**/*.java",
                "**/*.rb",
            ],
            "check": {"engine": "regex", "on": "added_lines", "within": "code", "pattern": pat},
            "message": f"Remove `{token}` (forbidden by the project instructions).",
            "fixtures": {
                "fail": [{"path": "src/fixture.py", "content": f"x = {token}\n"}],
                "pass": [{"path": "src/fixture.py", "content": "x = 1\n"}],
            },
        }
    ]


def _tool_substitution(m: re.Match[str], line: str) -> list[RuleBody]:
    good, bad = m.group("good").strip("`'\" "), m.group("bad").strip("`'\" ")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._+-]{0,30}", bad) or not re.fullmatch(
        r"[a-z0-9][a-z0-9._+ -]{0,40}", good
    ):
        return []
    return [
        {
            "title": f"Use {good} instead of {bad}",
            "severity": "required",
            "decidability": "deterministic",
            "scope": "command",
            "check": {
                "engine": "regex",
                "on": "command",
                "pattern": rf"(^|[;&|(]\s*|\s)({re.escape(bad)})(\s|$)",
            },
            "message": f"Use {good} instead of {bad}.",
            "fixtures": {
                "fail": [f"{bad} install", f"cd app && {bad} run build"],
                "pass": [f"{good} install", "ls -la"],
            },
        }
    ]


_PATH_TOKEN_RE = re.compile(
    r"`([^`\s]+)`|((?:[\w.-]*/[\w./*-]*)|(?:\.[A-Za-z][\w.-]*)|(?:[\w-]+\.(?:lock|ya?ml|json|toml|md|env|txt|cfg|ini|py|sh)))"
)


def _forbid_path(m: re.Match[str], line: str) -> list[RuleBody]:
    rest = line[m.start("path") :]
    tokens = []
    for code, plain in _PATH_TOKEN_RE.findall(rest):
        tok = (code or plain).strip("`'\" ,;:")
        if (
            tok
            and tok not in (".", "..")
            and not tok.startswith("http")
            and re.search(r"[/.]", tok)
        ):
            tokens.append(tok)
    tokens = list(dict.fromkeys(tokens))[:12]
    if not tokens:
        return []
    globs: list[str] = []
    for tok in tokens:
        base = tok.rstrip("/")
        is_file = bool(re.search(r"\.[A-Za-z0-9]+$", base)) and not tok.endswith("/")
        globs.extend([base] if is_file else [base, base + "/**"])
    first = tokens[0].rstrip("/")
    fail_path = (
        first
        if re.search(r"\.[A-Za-z0-9]+$", first) and not tokens[0].endswith("/")
        else first + "/x.txt"
    )
    return [
        {
            "title": "Do not modify " + ", ".join(tokens),
            "severity": "required",
            "decidability": "deterministic",
            "check": {
                "engine": "glob",
                "paths": globs,
                "change": ["added", "modified", "deleted", "renamed"],
            },
            "message": "Revert the change; the instructions forbid editing "
            + ", ".join(tokens)
            + ".",
            "fixtures": {"fail": [fail_path], "pass": ["unrelated/file.txt"]},
        }
    ]


def _docstring_cap(m: re.Match[str], line: str) -> list[RuleBody]:
    n = int(m.group("n"))
    body = "\n".join(['    """Line.'] + [f"    {i}" for i in range(2, n + 2)] + ['    """'])
    return [
        {
            "title": f"Docstring longer than {n} lines",
            "severity": "required",
            "decidability": "deterministic",
            "applies_to": ["**/*.py"],
            "check": {"engine": "ast", "rule": "docstring-max-lines", "max": n},
            "message": f"Shorten the docstring to at most {n} lines.",
            "fixtures": {
                "fail": [f"def f():\n{body}\n    return 1\n"],
                "pass": ['def f():\n    """Return one."""\n    return 1\n'],
            },
        }
    ]


def _function_cap(m: re.Match[str], line: str) -> list[RuleBody]:
    n = int(m.group("n"))
    long_fn = "def f():\n" + "".join(f"    x{i} = {i}\n" for i in range(n + 1))
    return [
        {
            "title": f"Function longer than {n} lines",
            "severity": "required",
            "decidability": "deterministic",
            "applies_to": ["**/*.py"],
            "check": {"engine": "ast", "rule": "function-max-lines", "max": n},
            "message": f"Split the function so each part is at most {n} lines.",
            "fixtures": {"fail": [long_fn], "pass": ["def f():\n    return 1\n"]},
        }
    ]


def _banned_word(m: re.Match[str], line: str) -> list[RuleBody]:
    words = re.findall(r"[\"“'`]([^\"”'`]{2,40})[\"”'`]", line)
    words = [w.strip() for w in words if w.strip()]
    if not words:
        return []
    pats = [r"\b" + re.escape(w) + r"\b" for w in words]
    return [
        {
            "title": "Banned word or phrase in prose",
            "severity": "advisory",
            "decidability": "deterministic",
            "applies_to": ["**/*.md", "**/*.py", "**/*.sh", "**/*.js", "**/*.ts", ":commit-msg"],
            "check": {
                "engine": "regex",
                "on": "added_lines",
                "within": "comments",
                "flags": ["i"],
                "patterns": pats,
            },
            "message": "Rephrase without: " + ", ".join(words) + ".",
            "fixtures": {
                "fail": [{"path": "docs/x.md", "content": f"This is {words[0]} here.\n"}],
                "pass": [{"path": "docs/x.md", "content": "Plain text.\n"}],
            },
        }
    ]


def _push_main(m: re.Match[str], line: str) -> list[RuleBody]:
    branch = m.group("branch")
    return [
        {
            "title": f"Direct push to {branch}",
            "severity": "critical",
            "decidability": "deterministic",
            "scope": "command",
            "check": {
                "engine": "regex",
                "on": "command",
                "pattern": rf"\bgit\b[^;&|\n]*\spush\b[^;&|\n]*\s(\S+\s+)?{branch}\b",
            },
            "message": f"Push to a feature branch and open a pull request instead of pushing to {branch}.",
            "fixtures": {
                "fail": [f"git push origin {branch}"],
                "pass": ["git push origin feature/x"],
            },
        }
    ]


def _line_length(m: re.Match[str], line: str) -> list[RuleBody]:
    n = int(m.group("n"))
    return [
        {
            "title": f"Line longer than {n} characters",
            "severity": "advisory",
            "decidability": "deterministic",
            "applies_to": ["**/*.py", "**/*.js", "**/*.ts", "**/*.go", "**/*.rs", "**/*.java"],
            "check": {"engine": "regex", "on": "added_lines", "pattern": rf"^.{{{n + 1},}}$"},
            "message": f"Wrap the line to at most {n} characters.",
            "fixtures": {
                "fail": [{"path": "src/fixture.py", "content": "x = '" + "a" * (n + 5) + "'\n"}],
                "pass": [{"path": "src/fixture.py", "content": "x = 1\n"}],
            },
        }
    ]


@dataclass(frozen=True)
class Template:
    id: str
    pattern: re.Pattern[str]
    build: Builder


def _t(tid: str, pattern: str, build: Builder) -> Template:
    return Template(tid, re.compile(pattern, re.IGNORECASE), build)


NEG = r"(never|do not|don['’]?t|dont|must not|should not|shouldn['’]?t|avoid|no)"

TEMPLATES: tuple[Template, ...] = (
    _t(
        "T-NO-VERIFY",
        rf"{NEG}\b.*(--no-verify|skip(ping)? (the )?(git |pre-commit )?hooks|bypass(ing)? (the )?hooks)",
        from_pack("SCP-004"),
    ),
    _t(
        "T-FORCE-PUSH",
        rf"{NEG}\b.*(force[- ]?push|--force\b)|\bpush\b.*--force",
        from_pack("SCP-005"),
    ),
    _t(
        "T-HISTORY",
        rf"{NEG}\b.*(rewrit\w* (git )?history|history[- ]rewrit|rebase|--amend|amend (a |the )?commit|reset --hard)",
        from_pack("SCP-006"),
    ),
    _t("T-RM-RF", rf"{NEG}\b.*rm -rf", from_pack("SCP-007")),
    _t(
        "T-PUSH-MAIN",
        rf"{NEG}\b.*(push|commit)\w* (directly )?(to|on|into) (the )?`?(?P<branch>main|master)`?\b",
        _push_main,
    ),
    _t("T-JQ", r"\bjq\b.*\bjson\b|\bjson\b.*\bjq\b", from_pack("SH-001")),
    _t(
        "T-CURL-SH",
        r"curl\s*\|\s*(ba)?sh|pip(e|ing)? .*(into|to) (a )?(ba)?sh",
        from_pack("SH-002"),
    ),
    _t("T-SUDO", rf"{NEG}\b.*\bsudo\b", from_pack("SH-003")),
    _t(
        "T-PRINT",
        rf"({NEG}\b.*\bprint(\(\))?(?!\w)|use (the )?logging\b.*instead of `?print|\bno `?print)",
        from_pack("HYG-002"),
    ),
    _t("T-BARE-EXCEPT", r"bare `?except|`?except:`?", from_pack("HYG-001")),
    _t("T-TODO", r"\btodo\b.*\b(issue|ticket|reference|link)\b", from_pack("HYG-003")),
    _t(
        "T-DOCSTRING",
        r"docstrings?\b.*?(≤|<=|<|\bunder|\bat most|\bno more than|\bmax(imum)?|\bless than|\bfewer than)\s*(?P<n>\d{1,2})\s*lines?",
        _docstring_cap,
    ),
    _t(
        "T-FUNC-LEN",
        r"functions?\b.*?(≤|<=|<|\bunder|\bat most|\bno more than|\bmax(imum)?|\bless than|\bfewer than)\s*(?P<n>\d{1,3})\s*lines?",
        _function_cap,
    ),
    _t(
        "T-LINE-LEN",
        r"(line length|lines?)\b.*?(≤|<=|<|\bunder|\bat most|\bno more than|\bmax(imum)?|\bless than)\s*(?P<n>\d{2,3})\s*(char(acter)?s|columns)",
        _line_length,
    ),
    _t(
        "T-DEPS",
        rf"{NEG}\b.*\b(add|install|introduce)\w*\b.*\b(new )?(dependenc(y|ies)|packages?|librar(y|ies))",
        from_pack("SCP-002", "SCP-008"),
    ),
    _t(
        "T-TESTS-RO",
        rf"({NEG}\b.*\b(modify|edit|change|delete|remove|weaken|rewrite|touch)\w*\b.*\btests?\b|tests? (are|is) read[- ]only)",
        from_pack("NAE-001"),
    ),
    _t("T-SKIP-TESTS", rf"{NEG}\b.*\b(skip|disable|xfail)\w*\b.*\btests?\b", from_pack("NAE-002")),
    _t(
        "T-HARDCODE",
        rf"{NEG}\b.*\bhard[- ]?cod\w*\b.*\b(expected|answers?|outputs?|results?|test)",
        from_pack("NAE-001", "NAE-003"),
    ),
    _t(
        "T-SECRETS",
        rf"{NEG}\b.*\b(commit|hard[- ]?code|check in|add|include|log|print|expose)\w*\b.*\b(secrets?|api keys?|credentials?|tokens?|passwords?|\.env)\b",
        from_pack("SEC-001"),
    ),
    _t(
        "T-RESTATE",
        r"comments? (that )?(restate|repeat|describe what|explain what)|(no|avoid|don['’]?t (add|write))\s+(redundant|obvious|unnecessary|excessive|verbose)\s+comments?",
        from_pack("HYG-006", "HYG-005"),
    ),
    _t(
        "T-BANNED-WORD",
        rf"{NEG}\b.*\b(say|use|write)\b.*\b(the )?(word|phrase|term)s?\b.*[\"“'`]",
        _banned_word,
    ),
    _t(
        "T-SUBST",
        r"\b(use|prefer)\s+(?P<good>`?[a-z0-9][a-z0-9._+ -]{0,40}?`?)\s*(,\s*not|instead of|rather than|over|not)\s+(?P<bad>`?[a-z0-9][a-z0-9._+-]{0,30}`?)",
        _tool_substitution,
    ),
    _t(
        "T-PATH",
        rf"{NEG}\s+(\w+\s+){{0,2}}?(edit|modify|change|touch|commit (changes )?to|write (to|into)|delete|overwrite)\w*\s+((the|any|files?|in|under|inside|within)\s+){{0,3}}(?P<path>`[^`]+`|[\w.-]*/[\w./*-]*|\.[A-Za-z][\w.-]*)",
        _forbid_path,
    ),
    _t(
        "T-VOICE",
        r"\b(filler (phrases?|words?)|verbal tics?|buzzwords?|fluff)\b",
        from_pack("VOI-001"),
    ),
    _t("T-FORBID-TOKEN", rf"{NEG}\b.*\buse\b.*`[^`]+`", _forbid_token),
)

HEURISTIC_HINTS = re.compile(
    r"(?i)\b(short|concise|small|brief|readable|simple|minimal|comments?|naming|names?|descriptive|"
    r"duplicat\w*|dry|consistent|idiomatic|type hints?|typed|typing|docstrings?|verbose|complex\w*|"
    r"nest\w*|magic numbers?|lines?|length|format\w*|style|import\w*|async|await|emoji|tone)\b"
)
