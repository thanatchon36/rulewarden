from __future__ import annotations

from pathlib import Path

import pytest

from rulewarden.config import Limits
from rulewarden.engine.checks import EngineContext, Target
from rulewarden.engine.checks import ast_check as astc
from rulewarden.engine.checks import glob_check as globc
from rulewarden.engine.checks import jq_check as jqc
from rulewarden.engine.checks import python_check as pyc
from rulewarden.engine.checks import regex_check as rx
from rulewarden.engine.checks import shell_check as shc
from rulewarden.engine.checks.comments import comment_text, style_for
from rulewarden.engine.diff import synthesize_added
from rulewarden.engine.schema import On
from rulewarden.errors import EngineError, SchemaError
from rulewarden.plugins import answers, hygiene

CTX = EngineContext(root=Path("."), limits=Limits())


def tgt(path: str, content: str) -> Target:
    fc = synthesize_added(path, content)
    return Target(path=path, status="added", content=content, added=fc.added, blocks=fc.blocks)


def test_comment_extraction() -> None:
    assert (
        style_for("a.py") == "hash"
        and style_for("x.ts") == "slash"
        and style_for("q.sql") == "dash"
    )
    assert (
        style_for("README.md") == "prose"
        and style_for(":commit-msg") == "prose"
        and style_for("Makefile") == "hash"
    )
    assert style_for("blob.bin") == "unknown"
    assert comment_text("a.py", "x = '#not' # yes") == " yes"
    assert comment_text("a.py", "x = 1") is None
    assert comment_text("a.sh", "#!/bin/sh") is None
    assert comment_text("a.ts", "let a = 1 // note") == " note"
    assert comment_text("a.ts", " * block line") is not None
    assert comment_text("a.ts", "let s = 'a//b'") is None
    assert comment_text("a.sql", "select 1 -- why") == " why"
    assert comment_text("a.bin", "x") is None
    assert comment_text("a.py", 'x = "a\\"#b"') is None


def test_regex_prepare_errors() -> None:
    with pytest.raises(SchemaError):
        rx.prepare({}, On.ADDED_LINES, CTX)
    with pytest.raises(SchemaError):
        rx.prepare({"pattern": "x", "mode": "maybe"}, On.ADDED_LINES, CTX)
    with pytest.raises(SchemaError, match="require"):
        rx.prepare({"pattern": "x", "mode": "require"}, On.ADDED_LINES, CTX)
    with pytest.raises(SchemaError):
        rx.prepare({"pattern": "x", "within": "nowhere"}, On.ADDED_LINES, CTX)
    with pytest.raises(SchemaError):
        rx.prepare({"pattern": "x", "unless": 3}, On.ADDED_LINES, CTX)
    with pytest.raises(SchemaError):
        rx.prepare({"pattern": "x", "detail": 3}, On.ADDED_LINES, CTX)
    with pytest.raises(SchemaError):
        rx.prepare({"pattern": "x", "bogus": 1}, On.ADDED_LINES, CTX)
    with pytest.raises(SchemaError):
        rx.prepare({"pattern": "x", "unless_changed": 3}, On.ADDED_LINES, CTX)
    assert rx.prepare(
        {"pattern": "x", "flags": "i", "unless_changed": "D.md"}, On.ADDED_LINES, CTX
    ).unless_changed == ("D.md",)


def test_regex_modes() -> None:
    p = rx.prepare(
        {"pattern": r"\bTODO\b", "unless": r"TODO\(#\d+\)", "within": "comments"},
        On.ADDED_LINES,
        CTX,
    )
    hits = rx.run(p, On.ADDED_LINES, tgt("a.py", "x = 'TODO'\n# TODO fix\n# TODO(#1) ok\n"), CTX)
    assert [h.line for h in hits] == [2]
    code = rx.prepare({"pattern": "print", "within": "code"}, On.ADDED_LINES, CTX)
    assert [
        h.line for h in rx.run(code, On.ADDED_LINES, tgt("a.py", "# print\nprint(1)\n"), CTX)
    ] == [2]
    hunks = rx.prepare({"pattern": r"a\nb"}, On.HUNKS, CTX)
    assert [h.line for h in rx.run(hunks, On.HUNKS, tgt("a.txt", "z\na\nb\n"), CTX)] == [2]
    req = rx.prepare({"pattern": "LICENSE", "mode": "require"}, On.FILE, CTX)
    assert rx.run(req, On.FILE, tgt("a.py", "x\n"), CTX)
    assert not rx.run(req, On.FILE, tgt("a.py", "# LICENSE\n"), CTX)
    file_forbid = rx.prepare({"pattern": "bad", "unless": "ok"}, On.FILE, CTX)
    assert [
        h.line for h in rx.run(file_forbid, On.FILE, tgt("a.py", "bad\nbad ok\nbad\n"), CTX)
    ] == [1, 3]
    path_rule = rx.prepare({"pattern": r"\.env$"}, On.PATH, CTX)
    assert rx.run(path_rule, On.PATH, Target(path="app/.env"), CTX)
    cmd = rx.prepare({"pattern": "sudo"}, On.COMMAND, CTX)
    assert rx.run(cmd, On.COMMAND, Target(path=":command", command="sudo ls"), CTX)
    assert not rx.run(cmd, On.COMMAND, Target(path=":command", command="ls"), CTX)
    need = rx.prepare({"pattern": "--dry-run", "mode": "require"}, On.COMMAND, CTX)
    assert rx.run(need, On.COMMAND, Target(path=":command", command="deploy"), CTX)
    assert rx.run(file_forbid, On.FILE, Target(path="x"), CTX) == []
    docs = rx.prepare({"pattern": "worth noting", "within": "comments"}, On.FILE, CTX)
    content = 'def f():\n    """It is worth noting."""\n    s = "worth noting"\n'
    assert [h.line for h in rx.run(docs, On.FILE, tgt("a.py", content), CTX)] == [2]
    assert rx._docstring_lines("def f(:\n  '''\n") == frozenset()
    companion = rx.prepare(
        {"pattern": "x", "unless_changed": ["DECISIONS.md"]}, On.ADDED_LINES, CTX
    )
    t = tgt("a.txt", "x\n")
    assert rx.run(companion, On.ADDED_LINES, t, CTX)
    t.changeset = ("DECISIONS.md",)
    assert not rx.run(companion, On.ADDED_LINES, t, CTX)


def test_regex_size_caps() -> None:
    small = EngineContext(root=Path("."), limits=Limits(max_line_chars=10, max_file_bytes=50))
    p = rx.prepare({"pattern": "x"}, On.ADDED_LINES, small)
    hits = rx.run(p, On.ADDED_LINES, tgt("a.txt", "y" * 20 + "\n"), small)
    assert hits and hits[0].unverifiable
    ph = rx.prepare({"pattern": "x"}, On.HUNKS, small)
    assert rx.run(ph, On.HUNKS, tgt("a.txt", "y" * 20 + "\n"), small)[0].unverifiable
    pf = rx.prepare({"pattern": "x"}, On.FILE, small)
    assert rx.run(pf, On.FILE, tgt("a.txt", "y" * 20 + "\n"), small)[0].unverifiable
    assert rx.run(pf, On.FILE, tgt("a.txt", "y\n" * 40), small)[0].unverifiable


def test_glob_engine() -> None:
    with pytest.raises(SchemaError):
        globc.prepare({}, On.PATH, CTX)
    for bad in (
        {"paths": 3},
        {"paths": ["x"], "mode": "x"},
        {"paths": ["x"], "change": ["moved"]},
        {"paths": ["x"], "exempt_if_locked": "yes"},
        {"paths_from": "elsewhere"},
        {"paths": ["x"], "unless_changed": 1},
    ):
        with pytest.raises(SchemaError):
            globc.prepare(bad, On.PATH, CTX)
    forbid = globc.prepare({"paths": "tests/**", "change": "deleted"}, On.PATH, CTX)
    assert globc.run(forbid, On.PATH, Target(path="tests/a.py", status="deleted"), CTX)
    assert not globc.run(forbid, On.PATH, Target(path="tests/a.py", status="modified"), CTX)
    allow = globc.prepare(
        {"paths": ["src/**"], "mode": "allow", "unless_changed": ["OK"]}, On.PATH, CTX
    )
    assert globc.run(allow, On.PATH, Target(path="infra/x.tf"), CTX)
    assert not globc.run(allow, On.PATH, Target(path="src/x.py"), CTX)
    assert not globc.run(allow, On.PATH, Target(path="infra/x.tf", changeset=("OK",)), CTX)
    prot = globc.prepare({"paths_from": "protected"}, On.PATH, CTX)
    ctx = EngineContext(root=Path("."), limits=Limits(), protected=(".claude/settings.json",))
    assert globc.run(prot, On.PATH, Target(path=".claude/settings.json"), ctx)


def test_ast_engine() -> None:
    with pytest.raises(SchemaError):
        astc.prepare({"rule": "nope"}, On.FILE, CTX)
    with pytest.raises(SchemaError):
        astc.prepare({"rule": "call"}, On.FILE, CTX)
    with pytest.raises(SchemaError):
        astc.prepare({"rule": "docstring-max-lines", "max": 0}, On.FILE, CTX)
    with pytest.raises(SchemaError):
        astc.prepare({"rule": "call", "names": "print"}, On.FILE, CTX)
    call = astc.prepare({"rule": "call", "names": ["print", "os.system"]}, On.FILE, CTX)
    hits = astc.run(
        call, On.FILE, tgt("a.py", "import os\nprint(1)\nos.system('x')\nf()(1)\n"), CTX
    )
    assert [h.line for h in hits] == [2, 3]
    imp = astc.prepare({"rule": "import", "names": ["pickle"]}, On.FILE, CTX)
    assert (
        len(
            astc.run(
                imp,
                On.FILE,
                tgt("a.py", "import pickle.x\nfrom pickle import y\nfrom . import z\n"),
                CTX,
            )
        )
        == 2
    )
    bare = astc.prepare({"rule": "bare-except"}, On.FILE, CTX)
    assert astc.run(bare, On.FILE, tgt("a.py", "try:\n    x()\nexcept:\n    pass\n"), CTX)
    swallow = astc.prepare({"rule": "broad-except-pass"}, On.FILE, CTX)
    assert astc.run(
        swallow, On.FILE, tgt("a.py", "try:\n    x()\nexcept Exception:\n    pass\n"), CTX
    )
    assert not astc.run(
        swallow, On.FILE, tgt("a.py", "try:\n    x()\nexcept ValueError:\n    pass\n"), CTX
    )
    doc = astc.prepare({"rule": "docstring-max-lines", "max": 2}, On.FILE, CTX)
    assert astc.run(doc, On.FILE, tgt("a.py", '"""a\nb\nc"""\nclass C:\n    """x"""\n'), CTX)
    fn = astc.prepare({"rule": "function-max-lines", "max": 2}, On.FILE, CTX)
    assert astc.run(fn, On.FILE, tgt("a.py", "def f():\n    a = 1\n    return a\n"), CTX)
    broken = astc.run(call, On.FILE, tgt("a.py", "def (:\n"), CTX)
    assert broken[0].unverifiable
    assert astc.run(call, On.FILE, Target(path="a.py"), CTX) == []
    small = EngineContext(root=Path("."), limits=Limits(max_file_bytes=5))
    assert astc.run(call, On.FILE, tgt("a.py", "print(1)\n"), small)[0].unverifiable


def test_jq_engine() -> None:
    with pytest.raises(SchemaError):
        jqc.prepare({"filter": ""}, On.FILE, CTX)
    p = jqc.prepare(
        {"filter": '(.dependencies // {}) | keys[] | "new dependency \\(.)"'}, On.FILE, CTX
    )
    hits = jqc.run(p, On.FILE, tgt("package.json", '{"dependencies": {"a": "1"}}'), CTX)
    assert [h.detail for h in hits] == ["new dependency a"]
    t = jqc.prepare({"filter": ".private == true", "detail": "private"}, On.FILE, CTX)
    assert jqc.run(t, On.FILE, tgt("p.json", '{"private": true}'), CTX)[0].detail == "private"
    assert jqc.run(t, On.FILE, tgt("p.json", "{not json"), CTX)[0].unverifiable
    assert jqc.run(t, On.FILE, Target(path="x"), CTX) == []
    bad = jqc.prepare({"filter": 'error("boom")'}, On.FILE, CTX)
    with pytest.raises(EngineError):
        jqc.run(bad, On.FILE, tgt("p.json", "{}"), CTX)


def test_jq_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jqc.shutil, "which", lambda _: None)
    p = jqc.prepare({"filter": "."}, On.FILE, CTX)
    with pytest.raises(EngineError, match="not on PATH"):
        jqc.run(p, On.FILE, tgt("p.json", "{}"), CTX)


def test_shell_engine() -> None:
    with pytest.raises(SchemaError):
        shc.prepare({"argv": "grep"}, On.FILE, CTX)
    p = shc.prepare(
        {"argv": ["grep", "-q", "forbidden"], "detail": "contains forbidden"}, On.FILE, CTX
    )
    with pytest.raises(EngineError, match="disabled"):
        shc.run(p, On.FILE, tgt("a.txt", "x"), CTX)
    off_list = EngineContext(
        root=Path("."), limits=Limits(), allow_shell=True, shell_allowlist=("cat",)
    )
    with pytest.raises(EngineError, match="allowlist"):
        shc.run(p, On.FILE, tgt("a.txt", "x"), off_list)
    ctx = EngineContext(
        root=Path("."),
        limits=Limits(),
        allow_shell=True,
        shell_allowlist=("grep", "sleep", "nosuchbin"),
    )
    assert shc.run(p, On.FILE, tgt("a.txt", "forbidden\n"), ctx) == []
    assert shc.run(p, On.FILE, tgt("a.txt", "fine\n"), ctx)[0].detail == "contains forbidden"
    assert shc.run(p, On.COMMAND, Target(path=":command", command=None), ctx) == []
    missing = shc.prepare({"argv": ["nosuchbin"]}, On.FILE, CTX)
    with pytest.raises(EngineError, match="not found"):
        shc.run(missing, On.FILE, tgt("a.txt", "x"), ctx)
    slow = shc.prepare({"argv": ["sleep", "5"]}, On.FILE, CTX)
    fast = EngineContext(
        root=Path("."), limits=Limits(per_check_s=0.2), allow_shell=True, shell_allowlist=("sleep",)
    )
    with pytest.raises(EngineError, match="timed out"):
        shc.run(slow, On.FILE, tgt("a.txt", "x"), fast)


def test_python_engine(tmp_path: Path) -> None:
    with pytest.raises(SchemaError):
        pyc.prepare({"plugin": 3}, On.FILE, CTX)
    with pytest.raises(SchemaError):
        pyc.prepare({"plugin": "nomodule"}, On.FILE, CTX)
    with pytest.raises(SchemaError):
        pyc.prepare({"plugin": "missing.fn"}, On.FILE, CTX)
    with pytest.raises(SchemaError):
        pyc.prepare({"plugin": "hygiene._private"}, On.FILE, CTX)
    with pytest.raises(SchemaError):
        pyc.prepare({"plugin": "hygiene.tokens", "options": []}, On.FILE, CTX)
    plugdir = tmp_path / ".rulewarden" / "plugins"
    plugdir.mkdir(parents=True)
    (plugdir / "mine.py").write_text(
        "from rulewarden.engine.checks import Hit\n"
        "def check(t, o):\n    return [Hit(1, 'mine')] if 'bad' in (t.content or '') else []\n"
        "def broken(t, o):\n    raise RuntimeError('x')\n"
        "def wrong(t, o):\n    return 'nope'\n",
        encoding="utf-8",
    )
    ctx = EngineContext(root=tmp_path, limits=Limits())
    p = pyc.prepare({"plugin": "local:mine.py:check"}, On.FILE, ctx)
    assert pyc.run(p, On.FILE, tgt("a.py", "bad\n"), ctx)[0].detail == "mine"
    with pytest.raises(EngineError):
        pyc.run(
            pyc.prepare({"plugin": "local:mine.py:broken"}, On.FILE, ctx),
            On.FILE,
            tgt("a.py", "x"),
            ctx,
        )
    with pytest.raises(EngineError):
        pyc.run(
            pyc.prepare({"plugin": "local:mine.py:wrong"}, On.FILE, ctx),
            On.FILE,
            tgt("a.py", "x"),
            ctx,
        )
    with pytest.raises(SchemaError):
        pyc.prepare({"plugin": "local:../../etc.py:x"}, On.FILE, ctx)
    with pytest.raises(SchemaError):
        pyc.prepare({"plugin": "local:mine.py:absent"}, On.FILE, ctx)


def test_hygiene_and_answers_plugins() -> None:
    hits = hygiene.restating_comment(tgt("a.py", "# increment counter\ncounter += 1\n"), {})
    assert hits and hits[0].line == 1
    assert not hygiene.restating_comment(
        tgt("a.py", "# vendor API is off by one\ncounter += 1\n"), {}
    )
    assert not hygiene.restating_comment(tgt("a.py", "# a\n# b\n"), {})
    assert not hygiene.restating_comment(Target(path="a.py"), {})
    assert hygiene.tokens("parseHTTPRequest_body") >= {"parse", "body"}
    dense = tgt("a.py", "".join(f"# c{i}\nx{i} = {i}\n" for i in range(5)))
    assert hygiene.comment_density(dense, {"max_ratio": 0.3})
    assert not hygiene.comment_density(dense, {"min_lines": 100})
    fake = "def f(n):\n    if n == 1:\n        return 2\n    if n in (3, 4):\n        return -1\n    return 0\n"
    assert answers.literal_lookup(tgt("a.py", fake), {})
    assert not answers.literal_lookup(tgt("a.py", fake), {"min_branches": 3})
    assert not answers.literal_lookup(tgt("a.py", "def (:\n"), {})
    assert not answers.literal_lookup(tgt("a.txt", fake), {})


def test_jq_planted_inside_repo_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = tmp_path / "ran"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "jq"
    fake.write_text(f"#!/bin/sh\ntouch {marker}\necho true\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:/usr/bin:/bin")
    ctx = EngineContext(root=tmp_path, limits=Limits())
    prep = jqc.prepare({"filter": ".a"}, On.FILE, ctx)
    with pytest.raises(EngineError, match="inside the repository"):
        jqc.run(prep, On.FILE, Target("x.json", content='{"a": 1}'), ctx)
    assert not marker.exists()
