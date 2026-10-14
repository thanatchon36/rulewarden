"""Determinism self-test payload: a fixed rule set and diff, evaluated and printed as canonical JSON.

Run as `python -m rulewarden.selftest`; doctor runs it in separate processes with different
TZ, locale and hash seeds and compares the output hashes byte for byte.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from rulewarden.config import Config
from rulewarden.engine.diff import parse_diff
from rulewarden.engine.loader import RuleSet, engine_context, load_rule_text, prepare_rules
from rulewarden.engine.report import to_json
from rulewarden.engine.runner import Request, run_check

RULES = """
version: 1
rules:
  - id: ST-001
    title: No print in library code
    severity: required
    decidability: deterministic
    applies_to: ["src/**/*.py"]
    check: {engine: ast, rule: call, names: [print]}
    message: Use logging instead of print().
    fixtures: {fail: ["print('x')"], pass: ["log.info('x')"]}
  - id: ST-002
    title: Use jq, not Python, for JSON in shell scripts
    severity: required
    decidability: deterministic
    applies_to: ["**/*.sh"]
    check: {engine: regex, pattern: 'python3?\\s+-c\\s+.*\\bjson\\b'}
    message: "Replace the Python one-liner with jq. Example: jq -r '.key' file.json"
    fixtures: {fail: ["python3 -c 'import json'"], pass: ["jq -r .k f.json"]}
  - id: ST-003
    title: Tests are read-only in this task
    severity: critical
    decidability: deterministic
    check: {engine: glob, paths: ["tests/**"], change: [modified, deleted]}
    message: Revert the change to the test file.
    fixtures: {fail: ["tests/test_a.py"], pass: ["src/a.py"]}
  - id: ST-004
    title: Avoid stock phrases
    severity: advisory
    decidability: deterministic
    applies_to: ["**/*.md", "**/*.py"]
    check: {engine: regex, pattern: '(?i)\\bper my last message\\b', within: comments}
    message: Delete the filler phrase.
    fixtures: {fail: ["# Per my last message, x"], pass: ["# x"]}
"""

DIFF = """diff --git a/src/pkg/mod.py b/src/pkg/mod.py
--- a/src/pkg/mod.py
+++ b/src/pkg/mod.py
@@ -1,0 +2,3 @@
+# Per my last message, ünïcode is fine
+def f(x):
+    print(x)
diff --git a/tools/sync.sh b/tools/sync.sh
--- a/tools/sync.sh
+++ b/tools/sync.sh
@@ -40,0 +41 @@
+python3 -c 'import json,sys; print(json.load(sys.stdin)["k"])' < f.json
diff --git a/tests/test_mod.py b/tests/test_mod.py
--- a/tests/test_mod.py
+++ b/tests/test_mod.py
@@ -3 +3 @@
-    assert f(1) == 2
+    assert True
"""

CONTENT = {
    "src/pkg/mod.py": "import x\n# Per my last message, ünïcode is fine\ndef f(x):\n    print(x)\n"
}


def payload() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Config(root=Path(tmp))
        rs = RuleSet(
            rules=prepare_rules(load_rule_text(RULES, "selftest"), engine_context(cfg)), files=()
        )
        diff = parse_diff(DIFF)
        for f in diff.files:
            f.new_content = CONTENT.get(f.path)
        res = run_check(
            cfg,
            Request(diff=diff, use_lock=False, check_protected_drift=False),
            ruleset=rs,
            bounded=True,
        )
        res.ruleset_sha256 = "selftest"
        return to_json(res)


if __name__ == "__main__":
    sys.stdout.write(payload())
