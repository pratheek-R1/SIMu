"""Portfolio-level validation: does the signal survive a 5-pick fund?

A student deploys five cheques. Five is a small number, so a sound strategy can
still blank. This Monte Carlo is what licenses the single most important design
decision in the scoring engine: fund P&L is weighted at exactly zero.

Scoring the outcome of a 5-pick fund would be scoring variance, not skill.

Run: python -m app.sim.portfolio
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import parameters as P
from .generator import FEATURE_INDEX, N_FEATURES

N_FUNDS = 20_000
DEAL_POOL = P.N_DEALS
PICKS = P.N_CHEQUES


@dataclass
class StrategyResult:
    name: str
    mean_wins: float
    p_zero_wins: float
    p_three_plus: float
    distribution: list[float]  # P(exactly k wins), k = 0..PICKS


def _simulate_pools(rng: np.random.Generator, n_funds: int):
    """Generate `n_funds` independent 40-company deal pools, outcome-first."""
    n_win = int(round(DEAL_POOL * P.DEAL_BASE_RATE))

    outcome = np.zeros((n_funds, DEAL_POOL), dtype=np.int8)
    outcome[:, :n_win] = 1
    # Independent shuffle per row.
    order = rng.random((n_funds, DEAL_POOL)).argsort(axis=1)
    outcome = np.take_along_axis(outcome, order, axis=1)

    flags = np.zeros((n_funds, DEAL_POOL, N_FEATURES), dtype=np.int8)
    for j, key in enumerate(P.FEATURE_KEYS):
        p_win, p_fail, _ = P.BINARY_FEATURES[key]
        p = np.where(outcome == 1, p_win, p_fail)
        flags[:, :, j] = (rng.random((n_funds, DEAL_POOL)) < p).astype(np.int8)

    return outcome, flags


def _top_k_wins(score: np.ndarray, outcome: np.ndarray, rng: np.random.Generator):
    """Pick the top PICKS by score per row, breaking ties at random."""
    jitter = rng.random(score.shape) * 1e-6
    idx = np.argsort(-(score + jitter), axis=1)[:, :PICKS]
    return np.take_along_axis(outcome, idx, axis=1).sum(axis=1)


def _summarise(name: str, wins: np.ndarray) -> StrategyResult:
    counts = np.bincount(wins, minlength=PICKS + 1)[: PICKS + 1]
    return StrategyResult(
        name=name,
        mean_wins=float(wins.mean()),
        p_zero_wins=float((wins == 0).mean()),
        p_three_plus=float((wins >= 3).mean()),
        distribution=[float(c / wins.size) for c in counts],
    )


def run(n_funds: int = N_FUNDS, seed: int = P.DEFAULT_SEED) -> list[StrategyResult]:
    rng = np.random.default_rng(seed + 104729)
    outcome, flags = _simulate_pools(rng, n_funds)

    causal_cols = [FEATURE_INDEX[k] for k in P.CAUSAL_FEATURES]
    trap_cols = [
        FEATURE_INDEX[k] for k in P.FEATURE_KEYS if P.feature_class(k) in ("B", "C")
    ]

    causal_score = flags[:, :, causal_cols].sum(axis=2).astype(np.float64)
    trap_score = flags[:, :, trap_cols].sum(axis=2).astype(np.float64)
    random_score = rng.random((n_funds, DEAL_POOL))

    return [
        _summarise("Picks on Class A causal variables", _top_k_wins(causal_score, outcome, rng)),
        _summarise("Picks on Class B/C trap variables", _top_k_wins(trap_score, outcome, rng)),
        _summarise("Picks at random", _top_k_wins(random_score, outcome, rng)),
    ]


def main() -> int:
    results = run()
    print(f"\nPORTFOLIO MONTE CARLO -- {N_FUNDS:,} funds of {PICKS} picks")
    print(f"from a {DEAL_POOL}-company deal flow at a {P.DEAL_BASE_RATE:.0%} true base rate")
    print("=" * 78)
    print(f"  {'strategy':<38}{'mean wins/5':>13}{'P(zero)':>10}{'P(3+)':>10}")
    for r in results:
        print(
            f"  {r.name:<38}{r.mean_wins:>13.2f}{r.p_zero_wins:>9.1%}{r.p_three_plus:>10.1%}"
        )

    causal, trap, rand = results
    print("\n" + "=" * 78)
    print(
        f"A trap-based strategy returns {trap.mean_wins:.2f} wins per fund against "
        f"{rand.mean_wins:.2f} for random picking."
    )
    if trap.mean_wins < rand.mean_wins:
        print("It performs WORSE than random. This is the whole point of the exercise.")
    print(
        f"A sound strategy still blanks roughly 1 fund in "
        f"{round(1 / causal.p_zero_wins) if causal.p_zero_wins else float('inf'):.0f}, "
        "which is why fund P&L is scored at zero weight."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
