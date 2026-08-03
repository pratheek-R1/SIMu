"""Dataset registry and public projections.

Two jobs:

1. Build a dataset once per seed and keep it in process memory. Generation is
   deterministic, so every worker that builds seed N gets a byte-identical
   dataset and no coordination is required.

2. Decide what a student is allowed to see, and when. This is the reason the
   simulation needs a backend at all. In the prototype the client generated the
   whole population including the `win` flag, so a student could read
   `portfolio[0].win` out of devtools and skip the entire exercise. Here the
   outcome never crosses the wire until the narrative has earned it:

     - winners             visible from the start (they are the seduction)
     - failures            only after the archive is unlocked, minus the withhold
     - withheld failures   never, at any point, to anyone
     - deal-flow outcomes  only after the fund is deployed
     - contradictions      only after the student flags one on that company
"""

from __future__ import annotations

from typing import Any

from .config import settings
from .sim import parameters as P
from .sim import profile as deep_profile
from .sim.generator import Dataset, build_dataset

_datasets: dict[int, Dataset] = {}
# Deep profiles are pure functions of (seed, company). Cached because a student
# opens the same profile repeatedly and regenerating is wasted work, not because
# the result could ever differ.
_deep_cache: dict[tuple[int, int], dict[str, Any]] = {}


def get_dataset(seed: int | None = None) -> Dataset:
    seed = seed if seed is not None else settings.default_cohort_seed
    if seed not in _datasets:
        _datasets[seed] = build_dataset(seed)
    return _datasets[seed]


# --------------------------------------------------------------------------
# Field groups
# --------------------------------------------------------------------------
# Never leaves the server under any circumstance until explicitly released.
SECRET_FIELDS = ("contradicts_feature", "contradiction_resolution")

ROW_FIELDS = (
    "id",
    "name",
    "sector",
    "city",
    "founded_year",
    "arr_usd",
    "month6_retention",
    "headcount",
    "ltv_cac_ratio",
    "burn_multiple",
)

PROFILE_FIELDS = ROW_FIELDS + (
    "flags",
    "gross_margin",
    "net_revenue_retention",
    "cac_payback_months",
    "arpu_monthly_usd",
    "customers",
    "monthly_churn",
    "avg_customer_lifetime_months",
    "ltv_usd",
    "cac_usd",
    "annual_payroll_usd",
    "gtm_spend_usd",
    "overhead_usd",
    "annual_opex_usd",
    "gross_profit_annual_usd",
    "annual_net_burn_usd",
    "net_new_arr_usd",
    "growth_rate",
    "total_raised_usd",
    "cash_on_hand_usd",
    "runway_months",
)

BALANCE_SHEET_FIELDS = tuple(
    f for f in (
        "bs_cash_c",
        "bs_accounts_receivable_c",
        "bs_prepaid_c",
        "bs_fixed_assets_c",
        "bs_total_assets_c",
        "bs_accounts_payable_c",
        "bs_accrued_payroll_c",
        "bs_deferred_revenue_c",
        "bs_venture_debt_c",
        "bs_total_liabilities_c",
        "bs_total_equity_c",
        "bs_paid_in_capital_c",
        "bs_accumulated_deficit_c",
    )
)


def _project(company: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {f: company[f] for f in fields if f in company}


def flags_to_dict(flags: str) -> dict[str, bool]:
    return {k: flags[i] == "1" for i, k in enumerate(P.FEATURE_KEYS)}


# --------------------------------------------------------------------------
# Projections
# --------------------------------------------------------------------------
def winner_rows(ds: Dataset) -> list[dict[str, Any]]:
    """The 500 companies the student researches. Table-level fields only."""
    out = []
    for cid in ds.winner_ids:
        c = ds.by_id(cid)
        assert c is not None
        row = _project(c, ROW_FIELDS)
        row["flags"] = c["flags"]
        out.append(row)
    return out


def archive_rows(ds: Dataset) -> list[dict[str, Any]]:
    """Failures, minus the withhold. Never includes withheld companies."""
    out = []
    for cid in ds.visible_failure_ids:
        c = ds.by_id(cid)
        assert c is not None
        row = _project(c, ROW_FIELDS)
        row["flags"] = c["flags"]
        out.append(row)
    return out


def competitors_for(ds: Dataset, cid: int) -> list[str]:
    """Three competitors named on a winner's profile, drawn from the FAILURE
    population.

    This is the thread a student can pull. The names appear in the fiction but
    return nothing from the research screen, because the research screen only
    contains winners. Noticing that -- and asking why -- is what the ghost-query
    provenance credit rewards. Selection is deterministic in the company id so a
    profile reads identically every time it is opened.
    """
    pool = ds.visible_failure_ids or ds.failure_ids
    if not pool:
        return []
    out = []
    for k in (1, 2, 3):
        pick = ds.by_id(pool[(cid * 7919 + k * 104729) % len(pool)])
        if pick and pick["name"] not in out:
            out.append(pick["name"])
    return out


def ghost_name_index(ds: Dataset) -> dict[str, int]:
    """Lowercased failure names -> id, for detecting a ghost query."""
    index = {}
    for cid in ds.failure_ids:
        c = ds.by_id(cid)
        if c:
            index[c["name"].lower()] = cid
    return index


def company_profile(
    ds: Dataset,
    cid: int,
    *,
    include_minutes: bool = False,
    include_interview: bool = False,
    reveal_contradiction: bool = False,
) -> dict[str, Any] | None:
    c = ds.by_id(cid)
    if c is None:
        return None

    profile = _project(c, PROFILE_FIELDS)
    profile["flag_map"] = flags_to_dict(c["flags"])
    # Strip the leading `bs_` and the TRAILING `_c` cents marker. An unanchored
    # replace also eats the `_c` inside `paid_in_capital_c`, which silently
    # renamed that line item and rendered it blank on the profile page.
    profile["balance_sheet"] = {
        f[len("bs_") : -len("_c")]: c[f] / 100.0 for f in BALANCE_SHEET_FIELDS
    }
    profile["balance_sheet_ties"] = (
        c["bs_total_assets_c"] == c["bs_total_liabilities_c"] + c["bs_total_equity_c"]
    )

    # The narrative sections are gated so that opening them is a real,
    # server-observable act rather than something that arrives free with the
    # profile. Triangulation depends on being able to tell the difference.
    if include_interview:
        profile["founder_interview"] = c["founder_interview"]
    if include_minutes:
        profile["board_minutes"] = c["board_minutes"]

    competitors = competitors_for(ds, cid)
    profile["competitors"] = competitors
    profile["deep"] = deep_for(ds, cid, competitors)

    if reveal_contradiction:
        profile["contradicts_feature"] = c["contradicts_feature"]
        profile["contradiction_resolution"] = c["contradiction_resolution"]

    return profile


def deep_for(ds: Dataset, cid: int, competitors: list[str] | None = None) -> dict[str, Any]:
    """Funding history, cap table, cohorts, press, reviews, market position.

    Every financial figure in here is read from the canonical model rather than
    redrawn, which is the whole reason it lives on the server.
    """
    key = (ds.seed, cid)
    if key not in _deep_cache:
        c = ds.by_id(cid)
        if c is None:
            return {}
        _deep_cache[key] = deep_profile.build(
            c, ds.seed, competitors if competitors is not None else competitors_for(ds, cid)
        )
    return _deep_cache[key]


def deal_rows(ds: Dataset, *, reveal_outcomes: bool = False) -> list[dict[str, Any]]:
    """The 40 live deals.

    `outcome` is withheld until the fund is deployed. The prototype shipped
    `outcome_hidden` to the client in the DF array, which meant the answer key
    was in the page source the whole time.
    """
    out = []
    for c in ds.deals:
        row = _project(c, ROW_FIELDS)
        row["flags"] = c["flags"]
        row["flag_map"] = flags_to_dict(c["flags"])
        row["gross_margin"] = c["gross_margin"]
        row["net_revenue_retention"] = c["net_revenue_retention"]
        row["cac_payback_months"] = c["cac_payback_months"]
        if reveal_outcomes:
            row["outcome"] = c["outcome"]
        out.append(row)
    return out


def feature_catalogue() -> list[dict[str, Any]]:
    """The variable list the client renders as chips. Class is NOT included --
    that would hand the student the answer key."""
    return [
        {"key": k, "label": P.FEATURE_LABELS[k]}
        for k in P.FEATURE_KEYS
    ]


def continuous_catalogue() -> list[dict[str, Any]]:
    return [
        {
            "key": k,
            "label": spec.label,
            "unit": spec.unit,
            "lower_is_better": spec.lower_is_better,
        }
        for k, spec in P.CONTINUOUS_FEATURES.items()
    ]


def evidence_board(ds: Dataset, variables: list[str]) -> list[dict[str, Any]]:
    """Supporting vs contradicting counts for the student's chosen variables.

    Counts are against the VISIBLE archive, because that is the evidence the
    student actually has. The complete-population figure is deliberately held
    back until the debrief, where the gap between the two is the second lesson.
    """
    rows = []
    for key in variables:
        counts = ds.feature_counts.get(key)
        if not counts:
            continue
        rows.append(
            {
                "feature": key,
                "label": P.FEATURE_LABELS[key],
                "supporting": counts["win"],
                "supporting_pct": round(counts["win"] / ds.n_winners * 100, 1),
                "contradicting": counts["fail_visible"],
                "contradicting_pct": round(
                    counts["fail_visible"] / ds.n_failures_visible * 100, 1
                ),
                "visible_lift": round(ds.sample_lift(key, visible_only=True), 2),
            }
        )
    return rows


def variable_evidence(ds: Dataset, *, archive_unlocked: bool) -> dict[str, Any]:
    """Per-variable evidence for the thesis screen.

    Before the archive arrives this returns prevalence and nothing else, because
    prevalence is genuinely all the student has: every company in the research
    set succeeded, so "win rate among companies with this trait" is 100% for
    every trait and the question cannot be asked. The client renders the
    win-rate bar as locked rather than hiding it -- the student should see the
    shape of the number they cannot have.

    After the archive unlocks, the same bars fill in against winners plus the
    visible failures.
    """
    rows = []
    for key in P.FEATURE_KEYS:
        counts = ds.feature_counts[key]
        row: dict[str, Any] = {
            "key": key,
            "label": P.FEATURE_LABELS[key],
            "count_portfolio": counts["win"],
            "pct_portfolio": round(counts["win"] / ds.n_winners * 100, 1),
            "win_rate_with": None,
            "win_rate_without": None,
            "lift": None,
        }
        if archive_unlocked:
            win_with = counts["win"]
            fail_with = counts["fail_visible"]
            win_without = ds.n_winners - win_with
            fail_without = ds.n_failures_visible - fail_with
            total_with = win_with + fail_with
            total_without = win_without + fail_without
            row["win_rate_with"] = (
                round(win_with / total_with * 100, 1) if total_with else None
            )
            row["win_rate_without"] = (
                round(win_without / total_without * 100, 1) if total_without else None
            )
            row["lift"] = round(ds.sample_lift(key, visible_only=True), 2)
        rows.append(row)

    return {
        "archive_unlocked": archive_unlocked,
        "portfolio_count": ds.n_winners,
        "archive_count": ds.n_failures_visible if archive_unlocked else None,
        "rows": rows,
    }


def truth_table(ds: Dataset) -> list[dict[str, Any]]:
    """Full ground truth. Debrief only -- never before."""
    ranking = {k: i + 1 for i, (k, _, _) in enumerate(ds.naive_ranking())}
    rows = []
    for key in P.FEATURE_KEYS:
        counts = ds.feature_counts[key]
        rows.append(
            {
                "feature": key,
                "label": P.FEATURE_LABELS[key],
                "class": P.feature_class(key),
                "pct_winners": round(counts["win"] / ds.n_winners * 100, 1),
                "pct_failures_visible": round(
                    counts["fail_visible"] / ds.n_failures_visible * 100, 1
                ),
                "pct_failures_complete": round(
                    counts["fail_complete"] / ds.n_failures_complete * 100, 1
                ),
                "visible_lift": round(ds.sample_lift(key, visible_only=True), 2),
                "true_lift": round(ds.sample_lift(key), 2),
                "rank_by_frequency": ranking[key],
            }
        )
    return rows


def continuous_truth(ds: Dataset) -> list[dict[str, Any]]:
    return [
        {
            "key": k,
            "label": P.CONTINUOUS_FEATURES[k].label,
            "unit": P.CONTINUOUS_FEATURES[k].unit,
            "lower_is_better": P.CONTINUOUS_FEATURES[k].lower_is_better,
            **{kk: round(vv, 4) for kk, vv in v.items()},
        }
        for k, v in ds.continuous_summary.items()
    ]


def scatter_points(ds: Dataset, *, include_failures: bool) -> dict[str, Any]:
    """Cross-plot data for the four continuous Class A metrics.

    These values come straight from the generator's calibrated draws. In the
    prototype the profile renderer computed its own gross margin / NRR / payback
    with different formulas, so the scatter tool and the profile page disagreed
    about the same company. There is one number system now.
    """

    def pack(ids: list[int]) -> list[list[float]]:
        pts = []
        for cid in ids:
            c = ds.by_id(cid)
            assert c is not None
            pts.append([round(c[k], 4) for k in P.CONTINUOUS_KEYS])
        return pts

    out: dict[str, Any] = {
        "axes": [
            {
                "key": k,
                "label": P.CONTINUOUS_FEATURES[k].label,
                "unit": P.CONTINUOUS_FEATURES[k].unit,
            }
            for k in P.CONTINUOUS_KEYS
        ],
        "winners": pack(ds.winner_ids),
        "failures": [],
        "failures_locked": not include_failures,
    }
    if include_failures:
        out["failures"] = pack(ds.visible_failure_ids)
    return out


def dataset_summary(ds: Dataset, *, archive_unlocked: bool) -> dict[str, Any]:
    """Headline figures for the dashboard.

    Before the archive arrives the student is told the portfolio size and
    nothing about what is missing. The denominator is the lesson.
    """
    winners = [ds.by_id(c) for c in ds.winner_ids]
    arrs = sorted(c["arr_usd"] for c in winners if c)
    rets = sorted(c["month6_retention"] for c in winners if c)
    ltvs = sorted(c["ltv_cac_ratio"] for c in winners if c)

    def median(xs: list[float]) -> float:
        n = len(xs)
        if not n:
            return 0.0
        mid = n // 2
        return xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2

    out = {
        "total_companies": ds.n_winners,
        "median_arr_usd": median(arrs),
        "median_retention": median(rets),
        "median_ltv_cac": median(ltvs),
        "archive_unlocked": archive_unlocked,
    }
    if archive_unlocked:
        out["archive_records"] = ds.n_failures_visible
        out["combined_records"] = ds.n_winners + ds.n_failures_visible
    return out
