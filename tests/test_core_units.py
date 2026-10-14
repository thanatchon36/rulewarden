from __future__ import annotations

import pytest

from rulewarden.engine.deviations import covering, parse_line, scan
from rulewarden.engine.diff import diff_between, parse_diff, synthesize_added
from rulewarden.engine.globs import glob_to_regex, match_any, match_path, selected
from rulewarden.engine.regexsafe import compile_safe
from rulewarden.engine.schema import Decidability, Severity, parse_rule, parse_rule_file
from rulewarden.errors import DiffError, SchemaError


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("**/*.py", "a.py", True),
        ("**/*.py", "src/x/a.py", True),
        ("*.py", "src/x/a.py", True),
        ("src/*.py", "src/x/a.py", False),
        ("src/**/*.py", "src/a.py", True),
        ("src/**", "src/a/b/c", True),
        (".github/workflows/**", ".github/workflows/ci.yml", True),
        ("./rules/", "rules/a.yaml", True),
        ("tests/", "tests/x.py", True),
        ("a?c", "abc", True),
        ("[ab].txt", "b.txt", True),
        ("[!ab].txt", "c.txt", True),
        ("[unclosed", "[unclosed", True),
        (":commit-msg", ":commit-msg", True),
        ("rules.lock", "rules.lock", True),
        ("rules.lock", "xrules.lock", False),
    ],
)
def test_globs(pattern: str, path: str, expected: bool) -> None:
    assert match_path(path, pattern) is expected


def test_glob_helpers() -> None:
    assert match_any("a/b.py", ["*.md", "**/*.py"])
    assert selected("src/a.py", ("src/**",), ("**/a.py",)) is False
    assert glob_to_regex("x") is glob_to_regex("x")


def test_synthetic_targets_need_explicit_selection() -> None:
    assert selected(":commit-msg", ("**",), ()) is False
    assert selected(":commit-msg", ("**/*.md", ":commit-msg"), ()) is True
    assert selected(":commit-msg", (":commit-msg",), (":commit-msg",)) is False


GIT_DIFF = """diff --git a/src/a.py b/src/a.py
index 111..222 100644
--- a/src/a.py
+++ b/src/a.py
@@ -1,2 +1,3 @@
 keep
-old
+new1
+new2
\\ No newline at end of file
diff --git a/new.txt b/new.txt
new file mode 100644
--- /dev/null
+++ b/new.txt
@@ -0,0 +1 @@
+hello
diff --git a/gone.txt b/gone.txt
deleted file mode 100644
--- a/gone.txt
+++ /dev/null
@@ -1 +0,0 @@
-bye
diff --git a/old name.txt b/new name.txt
similarity index 90%
rename from old name.txt
rename to new name.txt
diff --git a/img.png b/img.png
Binary files a/img.png and b/img.png differ
diff --git "a/q\\"x.txt" "b/q\\"x.txt"
--- "a/q\\"x.txt"
+++ "b/q\\"x.txt"
@@ -1 +1 @@
-a
+b
"""


def test_parse_git_diff() -> None:
    d = parse_diff(GIT_DIFF)
    by = d.by_path()
    a = by["src/a.py"]
    assert a.status == "modified"
    assert a.added == [(2, "new1"), (3, "new2")]
    assert a.removed == [(2, "old")]
    assert [b.start for b in a.blocks] == [2] and a.blocks[0].text == "new1\nnew2"
    assert by["new.txt"].status == "added" and by["new.txt"].added == [(1, "hello")]
    assert by["gone.txt"].status == "deleted"
    assert by["new name.txt"].status == "renamed" and by["new name.txt"].old_path == "old name.txt"
    assert by["img.png"].binary
    assert 'q"x.txt' in by
    assert len(d.raw_sha256) == 64


def test_parse_plain_unified_diff_and_octal_paths() -> None:
    text = "--- a/x.py\t2024-01-01\n+++ b/x.py\t2024-01-02\n@@ -1 +1,2 @@\n a\n+b\n"
    d = parse_diff(text)
    assert d.files[0].path == "x.py" and d.files[0].added == [(2, "b")]
    octal = 'diff --git "a/caf\\303\\251.txt" "b/caf\\303\\251.txt"\n--- "a/caf\\303\\251.txt"\n+++ "b/caf\\303\\251.txt"\n@@ -0,0 +1 @@\n+x\n'
    assert parse_diff(octal).files[0].path == "café.txt"


def test_parse_diff_errors() -> None:
    with pytest.raises(DiffError):
        parse_diff("diff --git a/x b/x\n@@ garbage @@\n")
    with pytest.raises(DiffError):
        parse_diff("diff --git nonsense\n")


def test_synthesize_and_between() -> None:
    fc = synthesize_added("a.txt", "x\ny\n")
    assert fc.added == [(1, "x"), (2, "y")] and fc.status == "added"
    assert synthesize_added("e.txt", "").blocks == []
    fc = diff_between("a.txt", "a\nb\nc\n", "a\nB\nc\nd\n")
    assert fc.added == [(2, "B"), (4, "d")]
    assert fc.removed == [(2, "b")]
    assert diff_between("a.txt", None, "z\n").status == "added"
    assert diff_between("a.txt", "z\n", None).status == "deleted"


def _rule(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "R-1",
        "title": "t",
        "severity": "required",
        "decidability": "deterministic",
        "check": {"engine": "regex", "pattern": "x"},
        "message": "m",
        "fixtures": {"fail": ["x"], "pass": ["y"]},
    }
    base.update(over)
    return base


def test_schema_accepts_valid_rule() -> None:
    r = parse_rule(_rule(), "f.yaml")
    assert r.severity is Severity.REQUIRED and r.decidability is Decidability.DETERMINISTIC
    assert r.applies_to == ("**",) and r.blocking
    assert parse_rule(_rule(severity="advisory"), "f").blocking is False


@pytest.mark.parametrize(
    ("over", "msg"),
    [
        ({"id": "bad id"}, "must match"),
        ({"severity": "high"}, "not one of"),
        ({"decidability": "heuristic"}, "may only be advisory"),
        ({"fixtures": {"fail": [], "pass": ["y"]}}, "failing fixture"),
        ({"fixtures": {"fail": ["x"]}}, "passing fixture"),
        ({"fixtures": {"fail": ["x"], "pass": ["y"], "maybe": []}}, "unknown keys"),
        ({"fixtures": "nope"}, "expected a mapping"),
        ({"extra": 1}, "unknown keys"),
        ({"check": None}, "missing check"),
        (
            {"check": {"engine": "regex", "on": "path", "pattern": "x"}, "scope": "command"},
            "requires check.on",
        ),
        ({"check": {"engine": "regex", "on": "command", "pattern": "x"}}, "requires scope"),
        ({"check": {"engine": "glob", "on": "file", "paths": ["x"]}}, "not valid for engine"),
        ({"check": "x"}, "expected a mapping"),
        ({"check": {1: 2, "engine": "regex"}}, "non-string keys"),
        ({"deviations": "maybe"}, "allowed"),
        ({"source": 3}, "source"),
        ({"title": ""}, "non-empty"),
        ({"applies_to": [1]}, "list of strings"),
    ],
)
def test_schema_rejects(over: dict[str, object], msg: str) -> None:
    with pytest.raises(SchemaError, match=msg):
        parse_rule(_rule(**over), "f.yaml")


def test_schema_misc() -> None:
    with pytest.raises(SchemaError, match="missing keys"):
        parse_rule({"id": "R-1"}, "f")
    with pytest.raises(SchemaError, match="must be a mapping"):
        parse_rule([], "f")
    u = parse_rule(
        {
            "id": "U-1",
            "title": "t",
            "severity": "advisory",
            "decidability": "undecidable",
            "message": "m",
        },
        "f",
    )
    assert u.check is None and u.fixtures is None
    with pytest.raises(SchemaError, match="never evaluated"):
        parse_rule(_rule(decidability="undecidable", severity="advisory"), "f")
    assert parse_rule(_rule(applies_to="*.py"), "f").applies_to == ("*.py",)
    yaml_on_true = _rule(check={"engine": "regex", True: "added_lines", "pattern": "x"})
    assert parse_rule(yaml_on_true, "f").check is not None
    with pytest.raises(SchemaError, match="top level"):
        parse_rule_file([], "f")
    with pytest.raises(SchemaError, match="version"):
        parse_rule_file({"version": 2, "rules": []}, "f")
    with pytest.raises(SchemaError, match="must be a list"):
        parse_rule_file({"version": 1, "rules": {}}, "f")
    with pytest.raises(SchemaError, match="unknown top-level"):
        parse_rule_file({"version": 1, "rules": [], "x": 1}, "f")


@pytest.mark.parametrize(
    "pattern", [r"(a+)+$", r"(a*)*b", r"(\w+\s?)*$", r"((ab)*c)*", r"(?:x+|y)+"]
)
def test_redos_screen_rejects_nested_repeats(pattern: str) -> None:
    with pytest.raises(SchemaError, match="ReDoS"):
        compile_safe(pattern)


def test_redos_screen_accepts_and_rejects_misc() -> None:
    assert compile_safe(r"python3?\s+-c\s+.*\bjson\b").search("python3 -c 'json'")
    assert compile_safe(r"(ab){2,3}x+").search("ababxx")
    assert compile_safe("a", ["i", "m", "s", "x"]).search("A")
    assert compile_safe(r"(?=a+)b|(?!c*)d").pattern
    with pytest.raises(SchemaError, match="backreferences"):
        compile_safe(r"(a)\1")
    with pytest.raises(SchemaError, match="invalid regex"):
        compile_safe("(")
    with pytest.raises(SchemaError, match="flag"):
        compile_safe("a", ["q"])
    with pytest.raises(SchemaError, match="longer"):
        compile_safe("a" * 3000)


def test_deviations_parse_and_cover() -> None:
    d = parse_line(
        "a.py",
        3,
        '# rulewarden: deviate R-1 reason="vendor" approved-by="@human" expires=2030-01-01',
    )
    assert (
        d is not None
        and d.rule_id == "R-1"
        and d.reason == "vendor"
        and str(d.expires) == "2030-01-01"
    )
    assert d.malformed == "" and len(d.fingerprint) == 64
    bad = parse_line("a.py", 1, "# rulewarden: deviate R-1 expires=nope")
    assert bad is not None and "missing reason" in bad.malformed and "bad expires" in bad.malformed
    assert parse_line("a.py", 1, "nothing here") is None
    devs = scan("a.py", "x = 1\n# rulewarden: deviate R-1 reason=x approved-by=@h\ny = 2\n")
    assert covering(devs, "R-1", 3) is not None
    assert covering(devs, "R-1", 2) is not None
    assert covering(devs, "R-1", 5) is None
    assert covering(devs, "R-2", 3) is None
    assert scan("a.py", "no marker") == []
