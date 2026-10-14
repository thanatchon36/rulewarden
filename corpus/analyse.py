"""RQ1 analysis: merge labels, compute shares, agreement and CIs; write data, tables, figures.

Offline: reads only corpus/data/. Outputs corpus/data/labels.{csv,parquet},
corpus/data/summary.json, paper/tables/corpus_*.md and paper/figures/corpus_*.png.
CIs are 95% percentile bootstraps that resample files (lines are nested in files).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ROOT = HERE.parent
TABLES = ROOT / "paper" / "tables"
FIGURES = ROOT / "paper" / "figures"
TIERS = ["deterministic", "heuristic", "undecidable"]
CATEGORIES = ["style", "tooling", "scope", "process", "testing", "security", "voice", "other"]
STRATA = ["CLAUDE.md", "AGENTS.md", ".cursorrules", "GEMINI.md", ".windsurfrules"]
SEED = 20261014
N_BOOT = 2000


def kappa(a: pd.Series, b: pd.Series) -> float:
    """Cohen's kappa for two label vectors over the same items."""
    cats = sorted(set(a) | set(b))
    n = len(a)
    if n == 0:
        return float("nan")
    po = float((a.to_numpy() == b.to_numpy()).mean())
    pa = a.value_counts(normalize=True)
    pb = b.value_counts(normalize=True)
    pe = float(sum(pa.get(c, 0.0) * pb.get(c, 0.0) for c in cats))
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def cluster_share_ci(df: pd.DataFrame, col: str, value: str) -> tuple[float, float, float]:
    """Point share of `value` in `col` and a file-cluster bootstrap 95% CI."""
    hits = (
        df.assign(_h=(df[col] == value).astype(int)).groupby("file_id")["_h"].agg(["sum", "count"])
    )
    s = hits["sum"].to_numpy()
    c = hits["count"].to_numpy()
    point = s.sum() / c.sum()
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(s), size=(N_BOOT, len(s)))
    boots = s[idx].sum(axis=1) / c[idx].sum(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return round(float(point), 4), round(float(lo), 4), round(float(hi), 4)


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def main() -> int:
    files = pd.read_csv(DATA / "files.csv", dtype=str)
    rules = pd.read_csv(DATA / "rules.csv", dtype=str, keep_default_na=False)
    rubric = pd.read_csv(DATA / "labels_rubric.csv", dtype=str, keep_default_na=False)
    df = rules.merge(rubric, on="rule_id", how="left")
    model_path = DATA / "labels_model.csv"
    has_model = model_path.exists()
    if has_model:
        model = pd.read_csv(model_path, dtype=str, keep_default_na=False)
        df = df.merge(model, on="rule_id", how="left")
    df = df.sort_values(["file_id", "rule_id"], kind="stable").reset_index(drop=True)
    df.to_csv(DATA / "labels.csv", index=False, lineterminator="\n")
    df.to_parquet(DATA / "labels.parquet", index=False)

    summary: dict[str, object] = {
        "n_files": len(files),
        "n_files_by_stratum": {s: int((files["stratum"] == s).sum()) for s in STRATA},
        "n_files_with_rules": int(df["file_id"].nunique()),
        "n_lines": len(df),
        "n_redacted": int((df["redacted"] == "1").sum()),
        "lines_per_file_median": float(
            df.groupby("file_id").size().reindex(files["file_id"], fill_value=0).median()
        ),
        "licences": files["license"].value_counts().sort_index().to_dict(),
    }
    log_path = DATA / "collection_log.json"
    if log_path.exists():
        summary["collection"] = json.loads(log_path.read_text(encoding="utf-8"))

    rub: dict[str, object] = {}
    for t in TIERS:
        p, lo, hi = cluster_share_ci(df, "decidability", t)
        rub[t] = {"share": p, "ci95": [lo, hi], "n": int((df["decidability"] == t).sum())}
    summary["rubric_decidability"] = rub
    summary["rubric_decidability_by_stratum"] = {
        s: {t: round(float((g["decidability"] == t).mean()), 4) if len(g) else None for t in TIERS}
        | {"n": len(g)}
        for s in STRATA
        for g in [df[df["stratum"] == s]]
    }
    summary["rubric_category"] = {
        c: {
            "share": round(float((df["category"] == c).mean()), 4),
            "n": int((df["category"] == c).sum()),
        }
        for c in CATEGORIES
    }
    ct = pd.crosstab(df["category"], df["decidability"]).reindex(
        index=CATEGORIES, columns=TIERS, fill_value=0
    )
    summary["rubric_category_by_decidability"] = {
        c: {t: int(ct.loc[c, t]) for t in TIERS} for c in CATEGORIES
    }
    compilable = df["compilable"] == "1"
    det = df["decidability"] == "deterministic"
    summary["compilable"] = {
        "share_all": round(float(compilable.mean()), 4),
        "n": int(compilable.sum()),
        "share_of_rubric_deterministic": round(float(compilable[det].mean()), 4)
        if det.any()
        else None,
        "templates": df.loc[compilable, "template"]
        .str.split("+")
        .explode()
        .value_counts()
        .to_dict(),
    }
    per_file = df.groupby("file_id")["decidability"].apply(lambda s: (s == "deterministic").mean())
    summary["per_file_deterministic_share"] = {
        "median": round(float(per_file.median()), 4),
        "q1": round(float(per_file.quantile(0.25)), 4),
        "q3": round(float(per_file.quantile(0.75)), 4),
        "files_with_no_deterministic_rule": int((per_file == 0).sum()),
    }

    if has_model:
        m = df[
            (df["redacted"] == "0") & (df["decidability_p1"] != "") & (df["decidability_p2"] != "")
        ]
        summary["model"] = {
            "n_labelled_both_passes": len(m),
            "kappa_p1_p2_decidability": round(kappa(m["decidability_p1"], m["decidability_p2"]), 4),
            "kappa_p1_p2_category": round(kappa(m["category_p1"], m["category_p2"]), 4),
            "kappa_rubric_p1_decidability": round(
                kappa(m["decidability"], m["decidability_p1"]), 4
            ),
            "kappa_rubric_p1_category": round(kappa(m["category"], m["category_p1"]), 4),
            "agreement_p1_p2_decidability": round(
                float((m["decidability_p1"] == m["decidability_p2"]).mean()), 4
            ),
            "decidability_p1": {},
        }
        mdec: dict[str, object] = {}
        for t in TIERS:
            p, lo, hi = cluster_share_ci(m, "decidability_p1", t)
            mdec[t] = {"share": p, "ci95": [lo, hi], "n": int((m["decidability_p1"] == t).sum())}
        summary["model"]["decidability_p1"] = mdec  # type: ignore[index]
        both = m[m["decidability_p1"] == m["decidability_p2"]]
        summary["model"]["consensus_decidability"] = {  # type: ignore[index]
            t: round(float((both["decidability_p1"] == t).mean()), 4) for t in TIERS
        } | {"n": len(both)}
        summary["model"]["category_p1"] = {  # type: ignore[index]
            c: round(float((m["category_p1"] == c).mean()), 4) for c in CATEGORIES
        }
        summary["model"]["kappa_p1_p2_is_rule"] = round(  # type: ignore[index]
            kappa(m["is_rule_p1"], m["is_rule_p2"]), 4
        )
        rules_only = m[(m["is_rule_p1"] == "1") & (m["is_rule_p2"] == "1")]
        ro: dict[str, object] = {
            "n_lines": len(rules_only),
            "share_of_lines": round(len(rules_only) / len(m), 4),
        }
        for col, key in (("decidability", "rubric"), ("decidability_p1", "model_p1")):
            tiers: dict[str, object] = {}
            for t in TIERS:
                p, lo, hi = cluster_share_ci(rules_only, col, t)
                tiers[t] = {"share": p, "ci95": [lo, hi], "n": int((rules_only[col] == t).sum())}
            ro[key] = tiers
        ro["kappa_rubric_p1_decidability"] = round(
            kappa(rules_only["decidability"], rules_only["decidability_p1"]), 4
        )
        ro["compilable_share"] = round(float((rules_only["compilable"] == "1").mean()), 4)
        summary["model"]["rules_only"] = ro  # type: ignore[index]
        conf = pd.crosstab(m["decidability"], m["decidability_p1"]).reindex(
            index=TIERS, columns=TIERS, fill_value=0
        )
        summary["model"]["confusion_rubric_rows_model_p1_cols"] = {  # type: ignore[index]
            r: {c: int(conf.loc[r, c]) for c in TIERS} for r in TIERS
        }
        agree = m[m["decidability"] == m["decidability_p1"]]
        summary["model"]["rubric_model_agreement"] = {  # type: ignore[index]
            "share": round(len(agree) / len(m), 4),
            "deterministic_by_both_share_of_all": round(
                float(
                    (
                        (m["decidability"] == "deterministic")
                        & (m["decidability_p1"] == "deterministic")
                    ).mean()
                ),
                4,
            ),
        }
        TABLES.mkdir(parents=True, exist_ok=True)
        lines = ["| Rubric \\ Model pass 1 | " + " | ".join(TIERS) + " |", "|---|---|---|---|"]
        lines += [
            f"| {r} | " + " | ".join(str(int(conf.loc[r, c])) for c in TIERS) + " |" for r in TIERS
        ]
        (TABLES / "corpus_confusion.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    (DATA / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_tables(df, summary, has_model)
    write_figures(df, has_model)
    print(json.dumps({k: summary[k] for k in ("n_files", "n_lines", "rubric_decidability")}))
    return 0


def write_tables(df: pd.DataFrame, summary: dict[str, object], has_model: bool) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    rub = summary["rubric_decidability"]
    assert isinstance(rub, dict)
    lines = [
        "| Tier | Rubric share (95% CI) | n |"
        + (" Model pass 1 share (95% CI) | n |" if has_model else ""),
        "|---|---|---|" + ("---|---|" if has_model else ""),
    ]
    model = summary.get("model", {})
    assert isinstance(model, dict)
    for t in TIERS:
        r = rub[t]
        row = f"| {t} | {pct(r['share'])} ({pct(r['ci95'][0])}–{pct(r['ci95'][1])}) | {r['n']} |"
        if has_model:
            mm = model["decidability_p1"][t]
            row += f" {pct(mm['share'])} ({pct(mm['ci95'][0])}–{pct(mm['ci95'][1])}) | {mm['n']} |"
        lines.append(row)
    (TABLES / "corpus_decidability.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    ct = pd.crosstab(df["category"], df["decidability"]).reindex(
        index=CATEGORIES, columns=TIERS, fill_value=0
    )
    out = ["| Category | n | share | " + " | ".join(TIERS) + " |", "|---|---|---|---|---|---|"]
    total = len(df)
    for c in CATEGORIES:
        n = int(ct.loc[c].sum())
        cells = " | ".join(pct(ct.loc[c, t] / n) if n else "–" for t in TIERS)
        out.append(f"| {c} | {n} | {pct(n / total) if total else '–'} | {cells} |")
    (TABLES / "corpus_categories.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def write_figures(df: pd.DataFrame, has_model: bool) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"svg.hashsalt": "rulewarden", "font.size": 9})
    colors = {"deterministic": "#1b7837", "heuristic": "#dfc27d", "undecidable": "#8c510a"}
    cols = ["decidability"] + (["decidability_p1"] if has_model else [])
    fig, axes = plt.subplots(
        1, len(cols), figsize=(3.6 * len(cols), 2.8), sharey=True, squeeze=False
    )
    for ax, col in zip(axes[0], cols, strict=True):
        sub = df[df[col] != ""] if col != "decidability" else df
        shares = pd.crosstab(sub["stratum"], sub[col], normalize="index").reindex(
            index=[s for s in STRATA if s in set(sub["stratum"])], columns=TIERS, fill_value=0
        )
        left = np.zeros(len(shares))
        for t in TIERS:
            ax.barh(shares.index, shares[t], left=left, color=colors[t], label=t)
            left += shares[t].to_numpy()
        ax.set_xlim(0, 1)
        ax.set_title("rubric" if col == "decidability" else "model (pass 1)")
        ax.invert_yaxis()
    axes[0][0].legend(
        loc="lower center", bbox_to_anchor=(0.5 * len(cols), -0.42), ncol=3, frameon=False
    )
    fig.tight_layout()
    fig.savefig(FIGURES / "corpus_decidability.png", dpi=200, metadata={"Software": None})
    plt.close(fig)

    counts = df["category"].value_counts().reindex(CATEGORIES, fill_value=0)
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    ax.bar(counts.index, counts.to_numpy(), color="#4d4d4d")
    ax.set_ylabel("rule-like lines")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(FIGURES / "corpus_categories.png", dpi=200, metadata={"Software": None})
    plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
