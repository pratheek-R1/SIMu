"""Outcome-first dataset generation.

The generation order matters and is not negotiable:

    for each company:
        outcome                         <- assigned first
        for each binary feature f:      value ~ Bernoulli(P(f | outcome))
        for each continuous feature f:  value ~ Normal(mu|outcome, sd|outcome)

Drawing the outcome first is what guarantees the ground-truth relationship
between every feature and the outcome is known exactly. Every downstream system
-- evidence board, debrief, scoring engine, portfolio simulation -- depends on
that guarantee.

Populations are fixed at exactly 500 winners and 2500 failures rather than drawn
from Bernoulli(1/6). A drawn count would make the headline validation numbers
(the 5-of-5 traps result) wobble between cohorts for no pedagogical benefit.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import finance, names, narrative, parameters as P

# --------------------------------------------------------------------------
# NOTE ON FEATURE COUNT
# --------------------------------------------------------------------------
# The handoff was internally inconsistent here: it refers throughout to "16
# binary features", a "16-character bitstring" and "16 weight sliders", but the
# BINARY_FEATURES table it quotes lists 18. The client's TAG_DEFS settles it at
# 16, which is what the parameter table now carries. Everything below derives
# the count from that table so the two can never drift again.
N_FEATURES = len(P.FEATURE_KEYS)
FEATURE_INDEX: dict[str, int] = {k: i for i, k in enumerate(P.FEATURE_KEYS)}


@dataclass
class Dataset:
    """An immutable, fully-realised cohort dataset."""

    seed: int
    fingerprint: str
    companies: list[dict[str, Any]]
    deals: list[dict[str, Any]]
    winner_ids: list[int]
    failure_ids: list[int]
    withheld_ids: list[int]
    visible_failure_ids: list[int]
    # {feature: {"win": n, "fail_complete": n, "fail_visible": n}}
    feature_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    # {metric: {"win_mean": x, "fail_mean": x, ...}}
    continuous_summary: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def n_winners(self) -> int:
        return len(self.winner_ids)

    @property
    def n_failures_complete(self) -> int:
        return len(self.failure_ids)

    @property
    def n_failures_visible(self) -> int:
        return len(self.visible_failure_ids)

    def by_id(self, cid: int) -> dict[str, Any] | None:
        """Look up any company, including deal-flow entries.

        Deal ids start at 900_001 so they can never collide with the main
        population. Returning them here lets a deal be rendered with the same
        profile machinery as a portfolio company -- an analyst should be able to
        read a live deal as closely as a historical one.
        """
        idx = cid - 1
        if 0 <= idx < len(self.companies) and self.companies[idx]["id"] == cid:
            return self.companies[idx]
        hit = next((c for c in self.companies if c["id"] == cid), None)
        if hit is not None:
            return hit
        return next((d for d in self.deals if d["id"] == cid), None)

    # ---- Ground-truth lift ---------------------------------------------
    def sample_lift(self, feature: str, *, visible_only: bool = False) -> float:
        """Realised lift for a feature: P(f | win) / P(f | fail).

        `visible_only=True` computes it against the post-withhold archive, i.e.
        what a student can actually observe. The default computes it against the
        complete failure population -- what was actually true.
        """
        c = self.feature_counts[feature]
        n_fail = self.n_failures_visible if visible_only else self.n_failures_complete
        fail_key = "fail_visible" if visible_only else "fail_complete"
        if n_fail == 0:
            return float("inf")
        p_win = c["win"] / self.n_winners
        p_fail = c[fail_key] / n_fail
        if p_fail == 0:
            return float("inf")
        return p_win / p_fail

    def naive_ranking(self) -> list[tuple[str, float, str]]:
        """The naive analyst procedure: rank binary features by raw frequency
        among winners. Returns [(feature, pct_of_winners, class)] descending."""
        rows = [
            (
                k,
                self.feature_counts[k]["win"] / self.n_winners,
                P.feature_class(k),
            )
            for k in P.FEATURE_KEYS
        ]
        rows.sort(key=lambda r: r[1], reverse=True)
        return rows


def _draw_binary(
    rng: np.random.Generator, outcome: np.ndarray
) -> np.ndarray:
    """Draw every binary feature conditional on outcome. Shape (n, N_FEATURES)."""
    n = outcome.shape[0]
    flags = np.zeros((n, N_FEATURES), dtype=np.int8)
    for j, key in enumerate(P.FEATURE_KEYS):
        p_win, p_fail, _ = P.BINARY_FEATURES[key]
        p = np.where(outcome == 1, p_win, p_fail)
        flags[:, j] = (rng.random(n) < p).astype(np.int8)
    return flags


def _draw_continuous(
    rng: np.random.Generator, outcome: np.ndarray
) -> dict[str, np.ndarray]:
    """Draw every continuous feature conditional on outcome, clipped to range."""
    n = outcome.shape[0]
    out: dict[str, np.ndarray] = {}
    for key, spec in P.CONTINUOUS_FEATURES.items():
        mean = np.where(outcome == 1, spec.mean_win, spec.mean_fail)
        sd = np.where(outcome == 1, spec.sd_win, spec.sd_fail)
        vals = rng.normal(mean, sd, n)
        out[key] = np.clip(vals, spec.clip_lo, spec.clip_hi)
    return out


def _select_withheld(
    rng: np.random.Generator, flags: np.ndarray, failure_pos: np.ndarray
) -> np.ndarray:
    """Choose which failures never surface, skewed toward pedigree.

    Companies with tier-one investors and elite-school founders are more likely
    to be quietly acqui-hired than to formally file dissolution paperwork, so
    they are systematically absent from a "recovered" archive. Weighted sampling
    without replacement via the Gumbel top-k trick.
    """
    k = int(round(len(failure_pos) * P.ARCHIVE_WITHHOLD_RATE))
    if k <= 0:
        return np.array([], dtype=np.int64)

    pedigree_cols = [FEATURE_INDEX[f] for f in P.PEDIGREE_FEATURES]
    pedigree_frac = flags[np.ix_(failure_pos, pedigree_cols)].mean(axis=1)
    weights = 1.0 + (P.ARCHIVE_WITHHOLD_PEDIGREE_SKEW - 1.0) * pedigree_frac

    keys = rng.random(len(failure_pos)) ** (1.0 / weights)
    chosen = np.argsort(-keys)[:k]
    return failure_pos[chosen]


def _assemble(
    ids: np.ndarray,
    outcome: np.ndarray,
    flags: np.ndarray,
    cont: dict[str, np.ndarray],
    fin: dict[str, np.ndarray],
    narr: dict[str, list],
    company_names: list[str],
    sectors: np.ndarray,
    cities: np.ndarray,
    years: np.ndarray,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for i in range(len(ids)):
        rec: dict[str, Any] = {
            "id": int(ids[i]),
            "name": company_names[i],
            "sector": P.SECTORS[int(sectors[i])],
            "city": P.CITIES[int(cities[i])],
            "founded_year": int(years[i]),
            "outcome": int(outcome[i]),
            "flags": "".join(str(int(b)) for b in flags[i]),
            "founder_interview": narr["founder_interview"][i],
            "board_minutes": narr["board_minutes"][i],
            "contradicts_feature": narr["contradicts_feature"][i],
            "contradiction_resolution": narr["contradiction_resolution"][i],
        }
        for key in P.CONTINUOUS_KEYS:
            rec[key] = float(cont[key][i])
        for key, arr in fin.items():
            val = arr[i]
            rec[key] = int(val) if key.endswith("_c") else float(val)
        records.append(rec)
    return records


def build_dataset(seed: int = P.DEFAULT_SEED) -> Dataset:
    """Build a complete cohort dataset. Deterministic in `seed`."""
    rng = np.random.default_rng(seed)
    n_total = P.N_WINNERS + P.N_FAILURES

    # ---- Outcome first --------------------------------------------------
    outcome = np.zeros(n_total, dtype=np.int8)
    outcome[: P.N_WINNERS] = 1
    rng.shuffle(outcome)

    flags = _draw_binary(rng, outcome)
    cont = _draw_continuous(rng, outcome)

    fin = finance.derive(
        rng,
        outcome=outcome,
        month6_retention=cont["month6_retention"],
        gross_margin=cont["gross_margin"],
        cac_payback_months=cont["cac_payback_months"],
        net_revenue_retention=cont["net_revenue_retention"],
        headcount_2x=flags[:, FEATURE_INDEX["headcountDoubled"]],
        expansion_customer_led=flags[:, FEATURE_INDEX["customerLed"]],
        usage_based_pricing=flags[:, FEATURE_INDEX["usageBased"]],
        series_a_above_20m=flags[:, FEATURE_INDEX["seriesA20"]],
    )

    ok, worst = finance.check_balance_sheet(fin)
    if not ok:
        raise AssertionError(
            f"balance sheet does not tie out; worst discrepancy {worst} cents"
        )

    narr = narrative.build(rng, n_total, flags, FEATURE_INDEX)

    all_names = names.generate_names(n_total + P.N_DEALS, seed)
    company_names = all_names[:n_total]
    deal_names = all_names[n_total:]

    sectors = rng.integers(0, len(P.SECTORS), n_total)
    # majorHub must agree with the city shown on the profile, or a student
    # can catch the dataset contradicting itself in one click.
    hub_flag = flags[:, FEATURE_INDEX["majorHub"]]
    hub_idx = np.array([P.CITIES.index(c) for c in P.HUB_CITIES])
    non_hub_idx = np.array(
        [i for i, c in enumerate(P.CITIES) if c not in P.HUB_CITIES]
    )
    cities = np.where(
        hub_flag == 1,
        hub_idx[rng.integers(0, len(hub_idx), n_total)],
        non_hub_idx[rng.integers(0, len(non_hub_idx), n_total)],
    )
    years = np.array(P.FOUNDED_YEARS)[rng.integers(0, len(P.FOUNDED_YEARS), n_total)]

    ids = np.arange(1, n_total + 1, dtype=np.int64)
    companies = _assemble(
        ids, outcome, flags, cont, fin, narr, company_names, sectors, cities, years
    )

    winner_pos = np.flatnonzero(outcome == 1)
    failure_pos = np.flatnonzero(outcome == 0)
    withheld_pos = _select_withheld(rng, flags, failure_pos)
    withheld_set = set(withheld_pos.tolist())
    visible_failure_pos = np.array(
        [p for p in failure_pos if p not in withheld_set], dtype=np.int64
    )

    # ---- Feature counts -------------------------------------------------
    feature_counts: dict[str, dict[str, int]] = {}
    for key in P.FEATURE_KEYS:
        col = flags[:, FEATURE_INDEX[key]]
        feature_counts[key] = {
            "win": int(col[winner_pos].sum()),
            "fail_complete": int(col[failure_pos].sum()),
            "fail_visible": int(col[visible_failure_pos].sum()),
        }

    continuous_summary: dict[str, dict[str, float]] = {}
    for key in P.CONTINUOUS_KEYS:
        vals = cont[key]
        continuous_summary[key] = {
            "win_mean": float(vals[winner_pos].mean()),
            "win_median": float(np.median(vals[winner_pos])),
            "fail_mean": float(vals[failure_pos].mean()),
            "fail_median": float(np.median(vals[failure_pos])),
            "fail_visible_mean": float(vals[visible_failure_pos].mean()),
        }

    deals = _build_dealflow(seed, deal_names)

    fingerprint = hashlib.sha256(
        f"{seed}:{n_total}:{N_FEATURES}:{P.N_DEALS}".encode()
    ).hexdigest()[:16]

    return Dataset(
        seed=seed,
        fingerprint=fingerprint,
        companies=companies,
        deals=deals,
        winner_ids=[int(ids[p]) for p in winner_pos],
        failure_ids=[int(ids[p]) for p in failure_pos],
        withheld_ids=[int(ids[p]) for p in withheld_pos],
        visible_failure_ids=[int(ids[p]) for p in visible_failure_pos],
        feature_counts=feature_counts,
        continuous_summary=continuous_summary,
    )


def build_backtest_pool(
    seed: int, n: int = 1000, base_rate: float = P.DEAL_BASE_RATE
) -> tuple[np.ndarray, np.ndarray]:
    """A held-out population for the model screen's live accuracy panel.

    The prototype reported model accuracy as `25 + Math.random()*20` -- a number
    with no relationship to the weights the student had just set, which meant
    the one screen that promised feedback gave none. This returns a real,
    fixed-per-seed population so the panel reports what the model would actually
    have done.

    Returns (flags, outcome) as arrays; the caller applies the weights.
    """
    rng = np.random.default_rng(seed + 31337)
    outcome = np.zeros(n, dtype=np.int8)
    outcome[: int(round(n * base_rate))] = 1
    rng.shuffle(outcome)
    return _draw_binary(rng, outcome), outcome


def _build_dealflow(seed: int, deal_names: list[str]) -> list[dict[str, Any]]:
    """The 40 live deals the student actually deploys into.

    Outcomes are drawn from the same conditional structure as the main
    population, so a model built on genuinely causal variables really does pick
    winners here. The winner count is fixed at exactly round(40 * 0.20) = 8
    rather than drawn, so no cohort receives a degenerate deal flow.
    """
    rng = np.random.default_rng(seed + 7919)
    n = P.N_DEALS

    outcome = np.zeros(n, dtype=np.int8)
    outcome[: int(round(n * P.DEAL_BASE_RATE))] = 1
    rng.shuffle(outcome)

    flags = _draw_binary(rng, outcome)
    cont = _draw_continuous(rng, outcome)
    fin = finance.derive(
        rng,
        outcome=outcome,
        month6_retention=cont["month6_retention"],
        gross_margin=cont["gross_margin"],
        cac_payback_months=cont["cac_payback_months"],
        net_revenue_retention=cont["net_revenue_retention"],
        headcount_2x=flags[:, FEATURE_INDEX["headcountDoubled"]],
        expansion_customer_led=flags[:, FEATURE_INDEX["customerLed"]],
        usage_based_pricing=flags[:, FEATURE_INDEX["usageBased"]],
        series_a_above_20m=flags[:, FEATURE_INDEX["seriesA20"]],
    )
    narr = narrative.build(rng, n, flags, FEATURE_INDEX)

    sectors = rng.integers(0, len(P.SECTORS), n)
    hub_flag = flags[:, FEATURE_INDEX["majorHub"]]
    hub_idx = np.array([P.CITIES.index(c) for c in P.HUB_CITIES])
    non_hub_idx = np.array([i for i, c in enumerate(P.CITIES) if c not in P.HUB_CITIES])
    cities = np.where(
        hub_flag == 1,
        hub_idx[rng.integers(0, len(hub_idx), n)],
        non_hub_idx[rng.integers(0, len(non_hub_idx), n)],
    )
    years = np.array(P.FOUNDED_YEARS)[rng.integers(0, len(P.FOUNDED_YEARS), n)]
    ids = np.arange(900_001, 900_001 + n, dtype=np.int64)

    return _assemble(
        ids, outcome, flags, cont, fin, narr, deal_names, sectors, cities, years
    )
