"""Run the pre-registered stages in order (bench/ANALYSIS_PLAN.md §1) until the budget is spent.

Usage: python -m bench.harness.schedule [--stages 1,2,...] [--workers 3]
Already-recorded runs are skipped, so the schedule can be resumed. An infrastructure
failure is retried once; the failed attempt stays recorded and counts against the budget.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from bench.harness import run as runner
from bench.harness import tasks


def stages(ids: list[str]) -> dict[int, list[tuple[str, str, int]]]:
    return {
        1: [(t, c, 1) for t in ids for c in ("B", "C")],
        2: [(t, "A", 1) for t in ids],
        3: [(t, c, 2) for t in ids for c in ("B", "C")],
        4: [(t, "D", 1) for t in ids],
        5: [(t, "E", 1) for t in ids[:10]],
        6: [(t, c, 3) for t in ids for c in ("B", "C")],
    }


def _one(job: tuple[str, str, int]) -> str:
    task, cond, rep = job
    out = runner.run_dir(task, cond, rep, pilot=False)
    if (out / "meta.json").exists():
        return f"skip {out.name} {task}"
    try:
        path = runner.run(task, cond, rep, pilot=False)
    except SystemExit as exc:
        return f"stop {task} {cond} r{rep}: {exc}"
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    if meta.get("infra_failure"):
        failed = path.with_name(path.name + ".infra1")
        path.rename(failed)
        try:
            path = runner.run(task, cond, rep, pilot=False)
        except SystemExit as exc:
            return f"stop {task} {cond} r{rep} retry: {exc}"
        meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    return (
        f"done {task} {cond} r{rep}: hidden={meta['hidden_exit']} turns={meta['result'].get('num_turns')}"
        f" wall={meta['wall_s']}s infra={meta['infra_failure']}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="1,2,3,4,5,6")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    plan = stages(tasks.all_ids())
    for s in [int(x) for x in a.stages.split(",")]:
        print(f"stage {s}: {len(plan[s])} jobs", flush=True)
        with ThreadPoolExecutor(a.workers) as pool:
            for line in pool.map(_one, plan[s]):
                print(line, flush=True)
        if runner.launched() >= runner.MAX_RUNS:
            print("budget reached", flush=True)
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
