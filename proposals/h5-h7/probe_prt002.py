"""Probe the patched PRT-002 pattern (from a patched copy given as argv[1]) against extra commands."""

import sys
from pathlib import Path

import yaml

from rulewarden.engine.regexsafe import compile_safe

pack = yaml.safe_load(Path(sys.argv[1]).read_text())
pat = compile_safe(next(r for r in pack["rules"] if r["id"] == "PRT-002")["check"]["pattern"])
CASES = {
    "cp a bench/rules/x.yaml": False,
    "mv x tools/rules/y": False,
    "rm -r bench/rules": False,
    "cat rules/a.yaml": False,
    "sed -i s/a/b/ rules/packs/voice.yaml": True,
    "echo x > rules/a.yaml": True,
    "echo x >rules/a.yaml": True,
    "cp a ./rules/x.yaml": True,
    "cp a 'rules/x.yaml'": True,
    'cp a "rules/x.yaml"': True,
    "rm rules.lock": True,
    "cp x .claude/settings.json": True,
}
misses = 0
for cmd, want in CASES.items():
    got = bool(pat.search(cmd))
    misses += got != want
    print(("ok  " if got == want else "MISS"), f"want={want} got={got}  {cmd}")
sys.exit(1 if misses else 0)
