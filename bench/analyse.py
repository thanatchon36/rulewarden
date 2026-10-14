"""Pre-registered analysis (bench/ANALYSIS_PLAN.md §3) over per-run rows from replay.py.

Unit: per-task mean over repeats; comparisons are paired by task. Wilcoxon signed-rank
(zero differences dropped; Pratt as sensitivity), median paired difference with a
percentile bootstrap 95% CI, matched-pairs rank-biserial r, Holm over the secondary family.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np
from scipy import stats

SEED = 20261014
N_BOOT = 10_000
CONDITIONS = ("A", "B", "C", "D", "E")


def task_means(rows: list[dict[str, Any]], cond: str, metric: str) -> dict[str, float]:
    acc: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r["condition"] == cond and not r["infra_failure"] and r.get(metric) not in (None, ""):
            acc[r["task"]].append(float(r[metric]))
    return {t: sum(v) / len(v) for t, v in acc.items()}


def paired(rows: list[dict[str, Any]], a: str, b: str, metric: str) -> dict[str, Any]:
    ma, mb = task_means(rows, a, metric), task_means(rows, b, metric)
    tasks = sorted(set(ma) & set(mb))
    x = np.array([ma[t] for t in tasks])
    y = np.array([mb[t] for t in tasks])
    out: dict[str, Any] = {
        "metric": metric,
        "comparison": f"{b} - {a}",
        "n_tasks": len(tasks),
        f"mean_{a}": round(float(x.mean()), 4) if len(x) else None,
        f"mean_{b}": round(float(y.mean()), 4) if len(y) else None,
        f"median_{a}": round(float(np.median(x)), 4) if len(x) else None,
        f"median_{b}": round(float(np.median(y)), 4) if len(y) else None,
    }
    if len(tasks) < 2:
        return out | {"p": None, "note": "fewer than 2 paired tasks"}
    d = y - x
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(d), size=(N_BOOT, len(d)))
    boots = np.median(d[idx], axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    out |= {
        "median_diff": round(float(np.median(d)), 4),
        "mean_diff": round(float(d.mean()), 4),
        "median_diff_ci95": [round(float(lo), 4), round(float(hi), 4)],
        "n_nonzero": int((d != 0).sum()),
    }
    if (d != 0).sum() == 0:
        return out | {
            "p": 1.0,
            "p_pratt": 1.0,
            "rank_biserial": 0.0,
            "note": "all differences zero",
        }
    w = stats.wilcoxon(y, x, zero_method="wilcox")
    wp = stats.wilcoxon(y, x, zero_method="pratt")
    nz = d[d != 0]
    ranks = stats.rankdata(np.abs(nz))
    r_plus, r_minus = ranks[nz > 0].sum(), ranks[nz < 0].sum()
    out |= {
        "W": float(w.statistic),
        "p": float(w.pvalue),
        "p_pratt": float(wp.pvalue),
        "rank_biserial": round(float((r_plus - r_minus) / (r_plus + r_minus)), 4),
    }
    return out


def holm(pvals: dict[str, float | None]) -> dict[str, float | None]:
    items = sorted(((p, k) for k, p in pvals.items() if p is not None and not math.isnan(p)))
    m = len(items)
    adj: dict[str, float | None] = {k: None for k in pvals}
    running = 0.0
    for i, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[k] = running
    return adj


def success_diff(rows: list[dict[str, Any]], a: str, b: str) -> dict[str, Any]:
    ma, mb = task_means(rows, a, "success"), task_means(rows, b, "success")
    tasks = sorted(set(ma) & set(mb))
    if not tasks:
        return {"n_tasks": 0}
    d = np.array([mb[t] - ma[t] for t in tasks])
    rng = np.random.default_rng(SEED)
    boots = d[rng.integers(0, len(d), size=(N_BOOT, len(d)))].mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {
        "comparison": f"{b} - {a}",
        "n_tasks": len(tasks),
        f"rate_{a}": round(float(np.mean([ma[t] for t in tasks])), 4),
        f"rate_{b}": round(float(np.mean([mb[t] for t in tasks])), 4),
        "diff": round(float(d.mean()), 4),
        "ci95": [round(float(lo), 4), round(float(hi), 4)],
        "margin": -0.10,
        "non_inferior": bool(lo > -0.10),
    }


def cells(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for c in CONDITIONS:
        sub = [r for r in rows if r["condition"] == c]
        if not sub:
            continue
        valid = [r for r in sub if not r["infra_failure"]]
        out[c] = {
            "runs": len(sub),
            "excluded_infra": len(sub) - len(valid),
            "tasks": len({r["task"] for r in valid}),
            "timed_out": sum(1 for r in valid if r["timed_out"]),
            "success_rate": round(float(np.mean([r["success"] for r in valid])), 4)
            if valid
            else None,
            "clean_rate": round(float(np.mean([r["clean"] for r in valid])), 4) if valid else None,
            "viol_det_total": int(sum(r["viol_det"] for r in valid)),
            "viol_heur_total": int(sum(r["viol_heur"] for r in valid)),
            "median_turns": float(np.median([r["turns"] or 0 for r in valid])) if valid else None,
            "median_wall_s": float(np.median([r["wall_s"] or 0 for r in valid])) if valid else None,
            "blocks_total": int(sum(r["blocks"] for r in valid)),
            "circumvention_attempts": int(sum(r["circumvention_attempts"] for r in valid)),
            "circumvention_blocked": int(sum(r["circumvention_blocked"] for r in valid)),
        }
    return out


def analyse(rows: list[dict[str, Any]], n_pilots: int = 0) -> dict[str, Any]:
    h1 = paired(rows, "B", "C", "viol_det")
    secondary = {
        "H2_viol_det_A_B": paired(rows, "A", "B", "viol_det"),
        "H3_viol_heur_B_C": paired(rows, "B", "C", "viol_heur"),
        "H5_turns_B_C": paired(rows, "B", "C", "turns"),
        "H5_tokens_B_C": paired(rows, "B", "C", "tokens"),
        "H5_wall_s_B_C": paired(rows, "B", "C", "wall_s"),
        "H6_cycles_C_D": paired(rows, "C", "D", "cycles_to_clean"),
        "H6_viol_det_C_D": paired(rows, "C", "D", "viol_det"),
    }
    adj = holm({k: v.get("p") for k, v in secondary.items()})
    for k, v in secondary.items():
        v["p_holm"] = adj[k]
    e = [r for r in rows if r["condition"] == "E" and not r["infra_failure"]]
    attempts = sum(r["circumvention_attempts"] for r in e)
    blocked = sum(r["circumvention_blocked"] for r in e)
    return {
        "n_runs": len(rows),
        "n_pilot_runs_excluded": n_pilots,
        "cells": cells(rows),
        "H1_viol_det_B_C": h1,
        "secondary": secondary,
        "H4_success_B_C": success_diff(rows, "B", "C"),
        "RQ5": {
            "runs": len(e),
            "attempts": attempts,
            "blocked": blocked,
            "share_blocked": round(blocked / attempts, 4) if attempts else None,
        },
    }
