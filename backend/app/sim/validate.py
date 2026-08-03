"""The go/no-go gate.

The dataset is the product. If the 500 winners do not reliably seduce a
competent analyst into a wrong theory, no amount of interface polish saves the
simulation. This module simulates the naive analyst procedure -- rank every
visible binary feature by raw frequency among the winners, take the top five --
and refuses to pass a parameter set that does not trap them.

Run this after ANY change to parameters.py, generator.py or finance.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import finance, parameters as P
from .generator import FEATURE_INDEX, Dataset, build_dataset


@dataclass
class GateResult:
    passed: bool
    seed: int
    naive_top5: list[dict] = field(default_factory=list)
    traps_in_top5: int = 0
    first_causal_rank: int = 0
    causal_lifts: list[dict] = field(default_factory=list)
    balance_sheet_ok: bool = False
    balance_sheet_worst_cents: int = 0
    burn_multiple: dict[str, float] = field(default_factory=dict)
    winner_metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    archive: dict[str, float] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def burn_multiple_report(ds: Dataset) -> dict[str, float]:
    """Burn multiple must discriminate lean companies from headcount-doublers.

    The handoff quotes ~3.5x lean vs ~6.3x doubled. That claim is about the
    profile pages a student actually reads, which are winners -- so the check is
    run on winners. Failures burn worse for a different reason (they are not
    growing), and mixing them in would mask the headcount effect being asserted.
    """
    j = FEATURE_INDEX["headcountDoubled"]
    lean, doubled = [], []
    for c in ds.companies:
        if c["outcome"] != 1:
            continue
        bm = c["burn_multiple"]
        if bm != bm or bm <= 0:  # NaN or non-meaningful
            continue
        (doubled if c["flags"][j] == "1" else lean).append(bm)
    return {
        "lean_median": float(np.median(lean)) if lean else float("nan"),
        "doubled_median": float(np.median(doubled)) if doubled else float("nan"),
        "lean_n": len(lean),
        "doubled_n": len(doubled),
    }


def winner_metric_report(ds: Dataset) -> dict[str, dict[str, float]]:
    """Winner-side medians must match the generator's calibrated distributions.

    This is the regression test for Open Issue 3. In the prototype the profile
    renderer re-derived gross margin, NRR and CAC payback with its own
    flag-conditioned formulas, drifting to 70 / 97 / 22 against a calibrated
    74 / 118 / 13. There is now exactly one number system, so this check should
    be trivially true -- which is the point of running it.
    """
    out: dict[str, dict[str, float]] = {}
    for key, spec in P.CONTINUOUS_FEATURES.items():
        vals = [c[key] for c in ds.companies if c["outcome"] == 1]
        out[key] = {
            "observed_median": float(np.median(vals)),
            "calibrated_mean": spec.mean_win,
            "drift": float(np.median(vals)) - spec.mean_win,
        }
    return out


def run_gate(seed: int = P.DEFAULT_SEED, ds: Dataset | None = None) -> GateResult:
    ds = ds or build_dataset(seed)
    failures: list[str] = []

    ranking = ds.naive_ranking()
    top5 = [
        {
            "rank": i + 1,
            "feature": k,
            "label": P.FEATURE_LABELS[k],
            "pct_of_winners": round(pct * 100, 1),
            "class": cls,
            "true_lift": round(ds.sample_lift(k), 2),
        }
        for i, (k, pct, cls) in enumerate(ranking[:5])
    ]

    traps_in_top5 = sum(1 for r in top5 if r["class"] in ("B", "C"))
    if traps_in_top5 < P.GATE_MIN_TRAPS_IN_TOP5:
        failures.append(
            f"only {traps_in_top5} of the naive top-5 are Class B/C traps; "
            f"gate requires at least {P.GATE_MIN_TRAPS_IN_TOP5}"
        )

    rank_of = {k: i + 1 for i, (k, _, _) in enumerate(ranking)}
    first_causal_rank = min(rank_of[k] for k in P.CAUSAL_FEATURES)
    if first_causal_rank < P.GATE_MIN_RANK_FIRST_CAUSAL:
        failures.append(
            f"first Class A feature ranks {first_causal_rank} by raw frequency; "
            f"gate requires rank {P.GATE_MIN_RANK_FIRST_CAUSAL} or worse"
        )

    causal_lifts = [
        {
            "feature": k,
            "label": P.FEATURE_LABELS[k],
            "lift": round(ds.sample_lift(k), 2),
            "rank_by_frequency": rank_of[k],
            "pct_of_winners": round(ds.feature_counts[k]["win"] / ds.n_winners * 100, 1),
        }
        for k in P.CAUSAL_FEATURES
    ]
    for row in causal_lifts:
        if row["lift"] < 2.0:
            failures.append(
                f"causal feature {row['feature']} has lift {row['lift']}x; "
                "expected a clear signal (>= 2.0x)"
            )

    # Rebuild the raw arrays only for the balance-sheet assertion.
    bs_arrays = {
        k: np.array([c[k] for c in ds.companies], dtype=np.int64)
        for k in (
            "bs_total_assets_c",
            "bs_total_liabilities_c",
            "bs_total_equity_c",
            "bs_paid_in_capital_c",
            "bs_accumulated_deficit_c",
        )
    }
    bs_ok, bs_worst = finance.check_balance_sheet(bs_arrays)
    if not bs_ok:
        failures.append(f"balance sheet off by {bs_worst} cents on at least one company")

    bm = burn_multiple_report(ds)
    if not (bm["doubled_median"] > bm["lean_median"] * 1.4):
        failures.append(
            f"burn multiple does not discriminate: lean {bm['lean_median']:.2f}x vs "
            f"doubled {bm['doubled_median']:.2f}x"
        )

    winner_metrics = winner_metric_report(ds)
    for key, row in winner_metrics.items():
        tol = P.CONTINUOUS_FEATURES[key].sd_win * 0.5
        if abs(row["drift"]) > tol:
            failures.append(
                f"winner-side {key} median {row['observed_median']:.3f} has drifted "
                f"from the calibrated {row['calibrated_mean']:.3f}"
            )

    # The withhold must actually bias the visible archive toward looking clean
    # on pedigree, or the second-order trap does not exist.
    pedigree_gap = []
    for f in P.PEDIGREE_FEATURES:
        complete = ds.feature_counts[f]["fail_complete"] / ds.n_failures_complete
        visible = ds.feature_counts[f]["fail_visible"] / ds.n_failures_visible
        pedigree_gap.append(complete - visible)
    archive = {
        "withheld": len(ds.withheld_ids),
        "visible": ds.n_failures_visible,
        "withhold_rate": round(len(ds.withheld_ids) / ds.n_failures_complete, 3),
        "mean_pedigree_understatement_pts": round(float(np.mean(pedigree_gap)) * 100, 2),
    }
    if archive["mean_pedigree_understatement_pts"] <= 0:
        failures.append("archive withhold is not skewed toward pedigree")

    return GateResult(
        passed=not failures,
        seed=seed,
        naive_top5=top5,
        traps_in_top5=traps_in_top5,
        first_causal_rank=first_causal_rank,
        causal_lifts=causal_lifts,
        balance_sheet_ok=bs_ok,
        balance_sheet_worst_cents=bs_worst,
        burn_multiple=bm,
        winner_metrics=winner_metrics,
        archive=archive,
        failures=failures,
    )


def main() -> int:
    res = run_gate()
    print(f"\nVALIDATION GATE -- seed {res.seed}")
    print("=" * 68)
    print("\nNaive analyst top 5 (rank binary features by frequency among winners):")
    print(f"  {'#':<3}{'feature':<34}{'% winners':>11}{'class':>7}{'lift':>8}")
    for r in res.naive_top5:
        flag = " <- trap" if r["class"] in ("B", "C") else ""
        print(
            f"  {r['rank']:<3}{r['label']:<34}{r['pct_of_winners']:>10.1f}%"
            f"{r['class']:>7}{r['true_lift']:>8.2f}{flag}"
        )
    print(f"\n  {res.traps_in_top5} of 5 top-ranked features are traps.")

    print("\nGenuinely predictive variables:")
    print(f"  {'feature':<34}{'lift':>8}{'rank by freq':>15}{'% winners':>12}")
    for r in sorted(res.causal_lifts, key=lambda x: -x["lift"]):
        print(
            f"  {r['label']:<34}{r['lift']:>7.2f}x{r['rank_by_frequency']:>15}"
            f"{r['pct_of_winners']:>11.1f}%"
        )
    print(f"\n  First Class A feature ranks {res.first_causal_rank} by raw frequency.")

    bm = res.burn_multiple
    print("\nFinancial reconciliation:")
    print(
        f"  balance sheet ties to the cent: {res.balance_sheet_ok} "
        f"(worst discrepancy {res.balance_sheet_worst_cents} cents)"
    )
    print(
        f"  burn multiple (winners) -- lean {bm['lean_median']:.2f}x (n={bm['lean_n']}) "
        f"vs doubled {bm['doubled_median']:.2f}x (n={bm['doubled_n']})"
    )
    print("  winner-side metrics against the calibrated distributions:")
    for key, row in res.winner_metrics.items():
        print(
            f"    {key:<26} observed {row['observed_median']:>7.3f}  "
            f"calibrated {row['calibrated_mean']:>7.3f}  drift {row['drift']:>+7.3f}"
        )

    a = res.archive
    print("\nArchive withhold (the second-order trap):")
    print(
        f"  {a['withheld']} of {a['withheld'] + a['visible']} failures withheld "
        f"({a['withhold_rate']:.1%})"
    )
    print(
        f"  visible archive understates pedigree among failures by "
        f"{a['mean_pedigree_understatement_pts']:.2f} pts on average"
    )

    print("\n" + "=" * 68)
    if res.passed:
        print("GATE: PASS")
        return 0
    print("GATE: FAIL")
    for f in res.failures:
        print(f"  - {f}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
