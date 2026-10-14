"""RQ3: safety-property test table and engine latency on this machine.

Runs the named pytest tests (junit XML) and times `run_check` on synthetic diffs with the
shipped packs. Writes bench/results/rq3.json and paper/tables/rq3_*.md. Latencies are
machine-specific; the hook latencies measured during the benchmark come from replay.py.
"""

from __future__ import annotations

import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "bench" / "results"
TABLES = ROOT / "paper" / "tables"

PROPERTIES: dict[str, list[str]] = {
    "Determinism across processes, TZ, locale, hash seed": [
        "tests/test_determinism_adversarial.py::test_report_identical_across_processes_and_environments",
        "tests/test_determinism_adversarial.py::test_doctor_selftest",
        "tests/test_determinism_adversarial.py::test_json_stable_under_input_reordering",
        "tests/test_report_audit_bounded.py::test_json_is_canonical",
    ],
    "ReDoS-shaped patterns rejected or killed": [
        "tests/test_determinism_adversarial.py::test_redos_pattern_cannot_load",
        "tests/test_determinism_adversarial.py::test_polynomial_regex_is_killed_by_budget",
        "tests/test_core_units.py::test_redos_screen_rejects_nested_repeats",
    ],
    "Oversized inputs fail closed": [
        "tests/test_determinism_adversarial.py::test_oversized_inputs_fail_closed",
        "tests/test_determinism_adversarial.py::test_long_line_is_unverifiable_not_ignored",
        "tests/test_runner.py::test_unverifiable_required_rule_blocks",
    ],
    "Corrupted rules and lock tampering fail closed": [
        "tests/test_determinism_adversarial.py::test_corrupted_rule_file_fails_closed",
        "tests/test_determinism_adversarial.py::test_lockfile_tampering",
        "tests/test_runner.py::test_missing_lock_fails_closed",
        "tests/test_runner.py::test_rule_edit_without_relock_fails_closed",
        "tests/test_determinism_adversarial.py::test_duplicate_ids_rejected",
    ],
    "Injected engine timeouts and crashes fail closed (blocking rules)": [
        "tests/test_determinism_adversarial.py::test_injected_engine_timeout_fails_closed",
        "tests/test_runner.py::test_engine_error_on_required_rule_fails_closed",
        "tests/test_runner.py::test_engine_error_on_advisory_rule_fails_open",
        "tests/test_report_audit_bounded.py::test_bounded_success_timeout_crash",
    ],
    "Protected-path edits blocked (diff, drift, shell)": [
        "tests/test_runner.py::test_protected_path_blocked_unless_locked",
        "tests/test_determinism_adversarial.py::test_protected_file_drift_detected_without_diff",
        "tests/test_determinism_adversarial.py::test_shell_bypass_attempts_on_protected_paths",
        "tests/test_runner.py::test_proposed_edit_of_locked_file_is_not_exempt",
        "tests/test_adapters.py::test_pretooluse_protects_monitor",
    ],
    "Agent-authored deviations of blocking rules rejected": [
        "tests/test_runner.py::test_agent_deviation_of_required_rule_is_critical",
        "tests/test_runner.py::test_deviation_expiry_and_forbidden",
        "tests/test_runner.py::test_deviation_advisory_by_listed_approver",
    ],
    "Audit log tamper-evident": ["tests/test_report_audit_bounded.py::test_audit_chain"],
}


def run_tests() -> dict[str, dict[str, object]]:
    ids = sorted({t for ts in PROPERTIES.values() for t in ts})
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "junit.xml"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={xml}",
                *ids,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        tree = ET.parse(xml)
    status: dict[str, bool] = {}
    for case in tree.iter("testcase"):
        name = case.get("name", "").split("[", 1)[0]
        cls = case.get("classname", "").replace(".", "/") + ".py"
        ok = not any(child.tag in ("failure", "error", "skipped") for child in case)
        key = f"{cls}::{name}"
        status[key] = status.get(key, True) and ok
    out: dict[str, dict[str, object]] = {}
    for prop, tests in PROPERTIES.items():
        found = [t for t in tests if t in status]
        out[prop] = {
            "tests": len(tests),
            "passed": sum(1 for t in found if status[t]),
            "missing": [t for t in tests if t not in status],
        }
    return out


def engine_latency(reps: int = 30) -> dict[str, dict[str, float]]:
    from rulewarden.config import load_config
    from rulewarden.engine.diff import Diff, synthesize_added
    from rulewarden.engine.runner import Request, run_check

    out: dict[str, dict[str, float]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".rulewarden").mkdir()
        (root / ".rulewarden" / "config.yaml").write_text(
            f"version: 1\nrules: [{ROOT / 'src' / 'rulewarden' / 'packs'}]\n"
        )
        (root / "packs").mkdir()
        cfg = load_config(root)
        body = "def f{i}(x):\n    # compute the value\n    return x + {i}\n"
        for n_lines in (10, 100, 1000):
            content = "".join(body.format(i=i) for i in range(n_lines // 3 + 1))
            diff = Diff(files=[synthesize_added("src/pkg/mod.py", content)], raw_sha256="x")
            times = []
            for _ in range(reps):
                t0 = time.perf_counter()
                run_check(cfg, Request(diff=diff, use_lock=False, check_protected_drift=False))
                times.append((time.perf_counter() - t0) * 1000)
            times.sort()
            out[f"{n_lines}_added_lines"] = {
                "p50": round(statistics.median(times), 1),
                "p95": round(times[int(0.95 * (len(times) - 1))], 1),
                "max": round(times[-1], 1),
            }
    return out


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    tests = run_tests()
    lat = engine_latency()
    data = {
        "safety_properties": tests,
        "engine_latency_ms": lat,
        "machine": {"python": platform.python_version(), "platform": platform.platform(terse=True)},
    }
    (RESULTS / "rq3.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rows = ["| Property | Tests passed |", "|---|---|"]
    rows += [f"| {p} | {v['passed']}/{v['tests']} |" for p, v in tests.items()]
    (TABLES / "rq3_safety.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    rows = ["| Change size | p50 ms | p95 ms | max ms |", "|---|---|---|---|"]
    rows += [
        f"| {k.replace('_', ' ')} | {v['p50']} | {v['p95']} | {v['max']} |" for k, v in lat.items()
    ]
    (TABLES / "rq3_latency.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    failed = [p for p, v in tests.items() if v["passed"] != v["tests"]]
    print(json.dumps(data["safety_properties"], indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
